// S152-08 — the themed shop's client-only rules (node --test).
// DRIFT NOTE — mirrored from vbwd-fe-user plugins/shop/shop:
//   addShopItem / updateShopQuantity / removeShopItem / shopItemCount — stores/cart.ts
//   add-to-cart feedback + "View Cart (n)"                          — views/ProductDetail.vue
//   quantity / remove buttons                                       — views/Cart.vue
//   badge count                                                     — components/CartBadge.vue
// The item shape is the theme runtime's SPA storage contract fixture.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { SHOP_CART_ITEMS } from '../../../theme/tests/js/fixtures/spa_storage_contract.mjs';

const RUNTIME_PATH = fileURLToPath(
  new URL('../../theme_shop/templates/shop/partials/shop_runtime.js', import.meta.url),
);
const plain = (value) => JSON.parse(JSON.stringify(value));

function node(attributes = {}, children = []) {
  const element = {
    attributes: { ...attributes },
    children,
    hidden: Object.prototype.hasOwnProperty.call(attributes, 'hidden'),
    disabled: Object.prototype.hasOwnProperty.call(attributes, 'disabled'),
    textContent: attributes.text || '',
    classList: {
      names: new Set((attributes.class || '').split(' ').filter(Boolean)),
      toggle(name, on) {
        if (on) this.names.add(name);
        else this.names.delete(name);
      },
    },
    getAttribute: (name) => (name in element.attributes ? element.attributes[name] : null),
    setAttribute: (name, value) => (element.attributes[name] = String(value)),
    matches: (selector) => {
      const match = selector.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/);
      if (match) {
        return match[2] === undefined ? match[1] in element.attributes : element.attributes[match[1]] === match[2];
      }
      return selector.startsWith('.') && element.classList.names.has(selector.slice(1));
    },
    querySelectorAll: (selector) => {
      const found = [];
      const visit = (current) =>
        current.children.forEach((child) => {
          if (child.matches(selector)) found.push(child);
          visit(child);
        });
      visit(element);
      return found;
    },
    querySelector: (selector) => element.querySelectorAll(selector)[0] || null,
    closest: (selector) => {
      for (let current = element; current; current = current.parent) {
        if (current.matches(selector)) return current;
      }
      return null;
    },
  };
  children.forEach((child) => (child.parent = element));
  return element;
}

function loadRuntime({ cart = [], body = node() } = {}) {
  const listeners = {};
  const writes = [];
  const timers = [];
  let stored = plain(cart);
  const document = {
    readyState: 'complete',
    addEventListener: (type, listener) => (listeners[type] = listeners[type] || []).push(listener),
    querySelectorAll: (selector) => body.querySelectorAll(selector),
    querySelector: (selector) => body.querySelector(selector),
  };
  const context = {
    document,
    localStorage: {},
    setTimeout: (callback, delay) => timers.push({ callback, delay }),
    VbwdTheme: {
      readCart: (storage, key) => (key === 'vbwd_shop_cart' ? plain(stored) : []),
      writeCart: (storage, doc, key, items) => {
        writes.push({ key, items: plain(items) });
        stored = plain(items);
      },
    },
    JSON,
  };
  context.window = context;
  vm.createContext(context);
  const source = readFileSync(RUNTIME_PATH, 'utf8');
  vm.runInContext(source, context);
  vm.runInContext(source, context);
  return { runtime: context.VbwdShop, listeners, writes, timers, body };
}

const ITEM = SHOP_CART_ITEMS[0];

test('installs once even when the partial is included several times', () => {
  const { listeners } = loadRuntime();

  assert.equal(listeners.click.length, 1);
});

test('adding merges by product + variant and caps at maxQuantity (cart.ts addItem)', () => {
  const { runtime } = loadRuntime();

  assert.deepEqual(plain(runtime.addShopItem([], { ...ITEM, quantity: 1 })), [{ ...ITEM, quantity: 1 }]);
  assert.deepEqual(
    plain(runtime.addShopItem([{ ...ITEM, quantity: 9 }], { ...ITEM, quantity: 4 })),
    [{ ...ITEM, quantity: 10 }],
  );
  const otherVariant = { ...ITEM, variantId: 'variant-red', quantity: 1 };
  assert.equal(runtime.addShopItem([{ ...ITEM }], otherVariant).length, 2);
  const noVariant = { ...ITEM, quantity: 1 };
  delete noVariant.variantId;
  assert.equal(runtime.addShopItem([{ ...noVariant }], { ...noVariant }).length, 1);
});

test('quantity updates clamp to 1..maxQuantity, removal and count follow cart.ts', () => {
  const { runtime } = loadRuntime();
  const items = [{ ...ITEM, quantity: 3 }];

  assert.equal(runtime.updateShopQuantity(items, 'product-mug', 0, 'variant-blue')[0].quantity, 1);
  assert.equal(runtime.updateShopQuantity(items, 'product-mug', 99, 'variant-blue')[0].quantity, 10);
  assert.deepEqual(plain(runtime.removeShopItem(items, 'product-mug', 'variant-blue')), []);
  assert.equal(runtime.removeShopItem(items, 'product-mug', undefined).length, 1);
  assert.equal(runtime.shopItemCount([{ quantity: 2 }, { quantity: 3 }]), 5);
});

test('an add-to-cart click writes the item, shows "Added!" for 2 s and reveals View Cart', () => {
  const button = node({ 'data-vbwd-shop-add': JSON.stringify({ ...ITEM, quantity: 1 }), 'data-added-label': 'Added!', text: 'Add to Cart' });
  const viewCart = node({ 'data-vbwd-shop-view-cart': '', 'data-label': 'View Cart', hidden: '' });
  const { listeners, writes, timers } = loadRuntime({ body: node({}, [button, viewCart]) });

  listeners.click[0]({ target: button, preventDefault() {} });
  listeners['vbwd:cart-changed'][0]({});

  assert.deepEqual(writes, [{ key: 'vbwd_shop_cart', items: [{ ...ITEM, quantity: 1 }] }]);
  assert.equal(button.textContent, 'Added!');
  assert.equal(button.disabled, true);
  assert.equal(viewCart.hidden, false);
  assert.equal(viewCart.textContent, 'View Cart (1)');
  assert.equal(timers[0].delay, 2000);
  timers[0].callback();
  assert.equal(button.textContent, 'Add to Cart');
  assert.equal(button.disabled, false);
});

test('a disabled add-to-cart button writes nothing', () => {
  const button = node({ 'data-vbwd-shop-add': '{}', disabled: '' });
  const { listeners, writes } = loadRuntime({ body: node({}, [button]) });

  listeners.click[0]({ target: button, preventDefault() {} });

  assert.deepEqual(writes, []);
});

test('the cart quantity and remove buttons rewrite the shop cart', () => {
  const increase = node({ 'data-vbwd-shop-quantity': '4', 'data-product-id': 'product-mug', 'data-variant-id': 'variant-blue' });
  const remove = node({ 'data-vbwd-shop-remove': '', 'data-product-id': 'product-mug', 'data-variant-id': 'variant-blue' });
  const { listeners, writes } = loadRuntime({ cart: [{ ...ITEM, quantity: 3 }], body: node({}, [increase, remove]) });

  listeners.click[0]({ target: increase, preventDefault() {} });
  listeners.click[0]({ target: remove, preventDefault() {} });

  assert.equal(writes[0].items[0].quantity, 4);
  assert.deepEqual(writes[1].items, []);
});

test('a line without a variant matches the empty data-variant-id', () => {
  const line = { ...ITEM, quantity: 2 };
  delete line.variantId;
  const remove = node({ 'data-vbwd-shop-remove': '', 'data-product-id': 'product-mug', 'data-variant-id': '' });
  const { listeners, writes } = loadRuntime({ cart: [line], body: node({}, [remove]) });

  listeners.click[0]({ target: remove, preventDefault() {} });

  assert.deepEqual(writes[0].items, []);
});

test('the badge shows the item count and hides on an empty cart', () => {
  const count = node({ class: 'cart-badge__count' });
  const badge = node({ 'data-vbwd-shop-cart-badge': '', hidden: '' }, [count]);
  const loaded = loadRuntime({ cart: [{ ...ITEM, quantity: 3 }], body: node({}, [badge]) });

  assert.equal(badge.hidden, false);
  assert.equal(count.textContent, '3');

  loaded.listeners.click[0]({ target: node(), preventDefault() {} });
  const empty = node({ 'data-vbwd-shop-cart-badge': '' }, [node({ class: 'cart-badge__count' })]);
  loadRuntime({ cart: [], body: node({}, [empty]) });
  assert.equal(empty.hidden, true);
});

test('a thumbnail click swaps the main image and the active thumbnail', () => {
  const image = node({ 'data-testid': 'product-detail-image', src: '/a.png' });
  const first = node({ 'data-vbwd-shop-thumb': '/a.png', class: 'product-detail__thumb product-detail__thumb--active' });
  const second = node({ 'data-vbwd-shop-thumb': '/b.png', class: 'product-detail__thumb' });
  const detail = node({ 'data-testid': 'product-detail' }, [image, first, second]);
  const { listeners } = loadRuntime({ body: node({}, [detail]) });

  listeners.click[0]({ target: second, preventDefault() {} });

  assert.equal(image.getAttribute('src'), '/b.png');
  assert.equal(second.classList.names.has('product-detail__thumb--active'), true);
  assert.equal(first.classList.names.has('product-detail__thumb--active'), false);
});
