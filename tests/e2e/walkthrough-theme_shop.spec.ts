/**
 * S152 walkthrough @theme_shop — a shopper on the themed storefront: the catalogue,
 * search + sort, a product page, add to cart (the header badge counts), quantity change
 * and removal in the cart, `/checkout?source=shop` by invoice, the confirmation, then the
 * order list and the order's detail page (the shop creates an order on payment capture, so
 * the merchant books the invoice as paid through the admin API first).
 *
 * Seeds (admin API, removed afterwards — the products only deactivated while the shop's
 * product DELETE fails): two products with stock in the default warehouse and a fresh buyer (force-deleted with the invoice and order it created). The
 * storefront pages themselves are the shop plugin's own CMS pages (`/shop`, `/shop/cart`).
 */
import { test, expect, type Page } from '@playwright/test';
import { uniqueSlug } from '@fe-user-e2e/frontend-mode/frontend-mode-support';
import {
  AdminSeeder,
  CONFIRMATION_URL_PATTERN,
  WalkthroughSteps,
  invoiceIdFromConfirmationUrl,
  loginInBrowser,
  skipUnlessThemeMode,
  type WalkthroughBuyer,
} from '../../../theme/tests/e2e/support/walkthrough-support';

const SHOP_ADMIN = '/api/v1/admin/shop';
const STOCK_QUANTITY = 50;

interface SeededProduct {
  id: string;
  slug: string;
  name: string;
}

async function seedProduct(seeder: AdminSeeder, name: string, price: number, warehouseId: string): Promise<SeededProduct> {
  const { product } = await seeder.send('POST', `${SHOP_ADMIN}/products`, {
    name,
    slug: uniqueSlug('walkthrough-product'),
    price,
    description: `${name}, seeded by a walkthrough.`,
    is_active: true,
  });
  seeder.onCleanup(() => removeProduct(seeder, product.id));
  await seeder.send('PUT', `${SHOP_ADMIN}/stock/${product.id}`, { warehouse_id: warehouseId, quantity: STOCK_QUANTITY });
  return { id: product.id, slug: product.slug, name: product.name };
}

/**
 * The shop's admin product DELETE answers 500 today (its routes hand the entity to
 * `BaseRepository.delete(id)` — a shop-plugin bug, recorded in the S152 report), so a
 * product that cannot be deleted is at least taken off the storefront.
 */
async function removeProduct(seeder: AdminSeeder, productId: string): Promise<void> {
  if (!(await seeder.deleteOrWarn(`${SHOP_ADMIN}/products/${productId}`))) {
    await seeder.send('PUT', `${SHOP_ADMIN}/products/${productId}`, { is_active: false });
  }
}

async function defaultWarehouseId(seeder: AdminSeeder): Promise<string> {
  const { warehouses } = await seeder.send('GET', `${SHOP_ADMIN}/warehouses`);
  const warehouse = warehouses.find((candidate: { is_default: boolean }) => candidate.is_default) ?? warehouses[0];
  if (!warehouse) {
    throw new Error('the shop has no warehouse (run the shop demo data seed)');
  }
  return warehouse.id;
}

async function payByInvoice(page: Page): Promise<void> {
  await page.fill('[data-testid="billing-first-name"]', 'Walk');
  await page.fill('[data-testid="billing-last-name"]', 'Shopper');
  await page.fill('[data-testid="billing-street"]', '2 Market Square');
  await page.fill('[data-testid="billing-city"]', 'Hamburg');
  await page.fill('[data-testid="billing-zip"]', '20095');
  await page.locator('[data-testid="billing-country"]').selectOption({ index: 1 });
  await page.locator('[data-testid="payment-method-invoice"]').click();
  await page.locator('[data-testid="terms-checkbox"] input[type="checkbox"]').check();
  await expect(page.locator('[data-testid="confirm-checkout"]')).toBeEnabled();
}

test.describe('Walkthrough @theme_shop — catalogue, product, cart, checkout, orders', () => {
  skipUnlessThemeMode(test);

  const steps = new WalkthroughSteps('theme_shop');
  const searchToken = `walkshop${Date.now()}`;
  let seeder: AdminSeeder;
  let cheapProduct: SeededProduct;
  let dearProduct: SeededProduct;
  let buyer: WalkthroughBuyer;

  test.beforeAll(async () => {
    seeder = await AdminSeeder.open();
    const warehouseId = await defaultWarehouseId(seeder);
    cheapProduct = await seedProduct(seeder, `Walkthrough ${searchToken} Lamp`, 12.5, warehouseId);
    dearProduct = await seedProduct(seeder, `Walkthrough ${searchToken} Desk`, 30, warehouseId);
    buyer = await seeder.freshBuyer();
  });

  test.afterAll(async () => {
    await seeder?.cleanup();
  });

  test('a shopper finds products, fills the cart, checks out and reviews the order @theme_shop', async ({ page }) => {
    await loginInBrowser(page, buyer);

    await page.goto('/shop');
    await expect(page.locator('[data-testid="product-catalog"]')).toBeVisible();
    await steps.themed(page, '01-catalogue');

    await page.fill('[data-testid="product-catalog-search"]', searchToken);
    const grid = page.locator('[data-testid="product-catalog-grid"]');
    await expect(grid.locator('[data-testid="product-card-name"]')).toHaveCount(2);
    await page.locator('[data-testid="product-catalog-sort"]').selectOption('price_desc');
    await expect(grid.locator('[data-testid="product-card-name"]').first()).toHaveText(dearProduct.name);
    await expect(grid.locator('[data-testid="product-card-name"]').last()).toHaveText(cheapProduct.name);
    await steps.themed(page, '02-search-and-sort');

    await page.locator(`[data-testid="product-card-${cheapProduct.slug}"]`).click();
    await page.waitForURL(`**/shop/product/${cheapProduct.slug}`);
    await expect(page.locator('[data-testid="product-detail-name"]')).toHaveText(cheapProduct.name);
    await expect(page.locator('[data-testid="product-detail-stock"]')).toBeVisible();
    await page.click('[data-testid="product-detail-add-to-cart"]');
    await expect(page.locator('[data-testid="cart-badge"] .cart-badge__count')).toHaveText('1');
    await steps.themed(page, '03-product-added');

    await page.goto(`/shop/product/${dearProduct.slug}`);
    await page.click('[data-testid="product-detail-add-to-cart"]');
    await expect(page.locator('[data-testid="cart-badge"] .cart-badge__count')).toHaveText('2');

    await page.goto('/shop/cart');
    await expect(page.locator('[data-testid="cart-item"]')).toHaveCount(2);
    const cheapLine = page.locator('[data-testid="cart-item"]', { hasText: cheapProduct.name });
    await cheapLine.locator('[data-testid="cart-item-increase"]').click();
    await expect(cheapLine.locator('[data-testid="cart-item-quantity"]')).toContainText('2');
    await page.locator('[data-testid="cart-item"]', { hasText: dearProduct.name }).locator('[data-testid="cart-item-remove"]').click();
    await expect(page.locator('[data-testid="cart-item"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="shopping-cart-subtotal"]')).toContainText('25');
    await steps.themed(page, '04-cart-updated');

    await page.click('[data-testid="shopping-cart-checkout"]');
    await page.waitForURL(/\/checkout\?source=shop/);
    await expect(page.locator('[data-testid="logged-in-email"]')).toContainText(buyer.email);
    await expect(page.locator('[data-testid="order-summary"]')).toContainText(cheapProduct.name);
    await payByInvoice(page);
    await steps.themed(page, '05-shop-checkout');
    await page.click('[data-testid="confirm-checkout"]');

    await page.waitForURL(CONFIRMATION_URL_PATTERN);
    await expect(page.locator('[data-testid="confirmation-banner"]')).toBeVisible();
    await expect(page.locator('[data-testid="line-item-row"]').first()).toContainText(cheapProduct.name);
    await steps.themed(page, '06-confirmation');

    // The shop creates the order on payment capture: the merchant books the bank transfer.
    await seeder.markInvoicePaid(invoiceIdFromConfirmationUrl(page.url()));

    await page.goto('/shop/orders');
    await expect(page.locator('[data-testid="order-row"]')).toHaveCount(1);
    await steps.themed(page, '07-order-list');
    await page.locator('[data-testid="order-row"] a').click();
    await page.waitForURL(/\/shop\/orders\/[0-9a-f-]+/);
    await expect(page.locator('[data-testid="order-detail-item-name"]').first()).toContainText(cheapProduct.name);
    await expect(page.locator('[data-testid="order-detail-number"]')).toBeVisible();
    await steps.themed(page, '08-order-detail');
  });
});
