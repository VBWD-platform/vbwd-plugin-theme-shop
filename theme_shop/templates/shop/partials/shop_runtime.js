/*
 * shop_runtime.js — the themed shop's client-only rules (S152-08), ES2019, inlined by the
 * shop widgets (installs once). It owns nothing but vbwd_shop_cart, through window.VbwdTheme:
 *   - [data-vbwd-shop-add] adds its CartItem (stores/cart.ts addItem), then shows the
 *     "Added!" feedback for 2 s (ProductDetail.vue handleAddToCart);
 *   - [data-vbwd-shop-quantity] / [data-vbwd-shop-remove] update / remove a cart line
 *     (Cart.vue); the cart island re-posts on the vbwd:cart-changed event;
 *   - [data-vbwd-shop-thumb] swaps the product image (ProductDetail.vue selectedImage);
 *   - [data-vbwd-shop-cart-badge] (CartBadge.vue) and [data-vbwd-shop-view-cart] show the
 *     item count, hidden while the cart is empty — on load, cart changes and region swaps.
 * Everything is delegated on document, so swapped islands and regions keep working.
 */
(function (window) {
  'use strict';
  if (window.VbwdShop) {
    return;
  }

  var SHOP_CART_KEY = 'vbwd_shop_cart';
  var FEEDBACK_MILLISECONDS = 2000;
  var ACTIVE_THUMB_CLASS = 'product-detail__thumb--active';

  function sameLine(item, productId, variantId) {
    return item.productId === productId && (item.variantId || undefined) === (variantId || undefined);
  }

  function addShopItem(items, input) {
    var next = items.map(function (item) {
      return Object.assign({}, item);
    });
    var existing = next.filter(function (item) {
      return sameLine(item, input.productId, input.variantId);
    })[0];
    if (existing) {
      existing.quantity = Math.min(existing.quantity + input.quantity, input.maxQuantity);
    } else {
      next.push(Object.assign({}, input));
    }
    return next;
  }

  function updateShopQuantity(items, productId, quantity, variantId) {
    return items.map(function (item) {
      if (!sameLine(item, productId, variantId)) return item;
      return Object.assign({}, item, { quantity: Math.max(1, Math.min(quantity, item.maxQuantity)) });
    });
  }

  function removeShopItem(items, productId, variantId) {
    return items.filter(function (item) {
      return !sameLine(item, productId, variantId);
    });
  }

  function shopItemCount(items) {
    return items.reduce(function (sum, item) {
      return sum + item.quantity;
    }, 0);
  }

  function readShopCart() {
    return window.VbwdTheme.readCart(window.localStorage, SHOP_CART_KEY);
  }

  function writeShopCart(items) {
    window.VbwdTheme.writeCart(window.localStorage, window.document, SHOP_CART_KEY, items);
  }

  function refreshCounts() {
    var count = shopItemCount(readShopCart());
    window.document.querySelectorAll('[data-vbwd-shop-cart-badge]').forEach(function (badge) {
      badge.hidden = count === 0;
      badge.querySelector('.cart-badge__count').textContent = String(count);
    });
    window.document.querySelectorAll('[data-vbwd-shop-view-cart]').forEach(function (link) {
      link.hidden = count === 0;
      link.textContent = link.getAttribute('data-label') + ' (' + count + ')';
    });
  }

  function addToCart(button) {
    if (button.disabled) return;
    writeShopCart(addShopItem(readShopCart(), JSON.parse(button.getAttribute('data-vbwd-shop-add'))));
    var label = button.textContent;
    button.textContent = button.getAttribute('data-added-label');
    button.disabled = true;
    window.setTimeout(function () {
      button.textContent = label;
      button.disabled = false;
    }, FEEDBACK_MILLISECONDS);
  }

  function changeLine(control) {
    var productId = control.getAttribute('data-product-id');
    var variantId = control.getAttribute('data-variant-id');
    var items = readShopCart();
    if (control.getAttribute('data-vbwd-shop-remove') !== null) {
      writeShopCart(removeShopItem(items, productId, variantId));
      return;
    }
    writeShopCart(updateShopQuantity(items, productId, Number(control.getAttribute('data-vbwd-shop-quantity')), variantId));
  }

  function showImage(thumb) {
    var detail = thumb.closest('[data-testid="product-detail"]');
    detail.querySelector('[data-testid="product-detail-image"]').setAttribute('src', thumb.getAttribute('data-vbwd-shop-thumb'));
    detail.querySelectorAll('[data-vbwd-shop-thumb]').forEach(function (other) {
      other.classList.toggle(ACTIVE_THUMB_CLASS, other === thumb);
    });
  }

  function handleClick(event) {
    var target = event.target;
    if (!target || !target.closest) return;
    var addButton = target.closest('[data-vbwd-shop-add]');
    if (addButton) return addToCart(addButton);
    var lineControl = target.closest('[data-vbwd-shop-quantity]') || target.closest('[data-vbwd-shop-remove]');
    if (lineControl) return changeLine(lineControl);
    var thumb = target.closest('[data-vbwd-shop-thumb]');
    if (thumb) showImage(thumb);
  }

  window.document.addEventListener('click', handleClick);
  window.document.addEventListener('vbwd:cart-changed', refreshCounts);
  window.document.addEventListener('vbwd:regions-swapped', refreshCounts);
  if (window.document.readyState === 'loading') {
    window.document.addEventListener('DOMContentLoaded', refreshCounts);
  } else {
    refreshCounts();
  }

  window.VbwdShop = Object.freeze({
    addShopItem: addShopItem,
    updateShopQuantity: updateShopQuantity,
    removeShopItem: removeShopItem,
    shopItemCount: shopItemCount
  });
})(window);
