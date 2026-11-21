# Public review endpoints: Indian skincare stores (sunscreen PDPs)

Verified 2026-11-21 by watching each product page's own network calls in a real browser, then calling the endpoint again with curl. Every row below returned real review JSON. Nothing here is inferred unless it is marked "not verified".

## General notes

- **Shopify storefront HTML rate limit.** After roughly 10 `products.json` calls, plain curl to `/products/{handle}` returned HTTP 429 ("Too many requests") on every Shopify store from this IP. The review hosts (judge.me, yotpo, nector) were **not** throttled. Get product ids from `https://{domain}/products.json?limit=250` (field `products[].id`) or `/products/{handle}.json`, with ≥2 s between calls. You do not need to scrape the PDP HTML.
- **Product id = Shopify product id** (the `id` in products.json) for Judge.me, Yotpo and Nector. Foxtale is the exception (see below).
- Use a browser User-Agent. No cookies or auth headers are needed except Nector's `x-apikey`, which is public and embedded in the page.
- Many SKUs (mini sizes, "pack of 2", "-copy") have 0 or very few reviews. Use the main SKU, or sum across SKUs.

## Summary

| Store | Provider | Shop key | Endpoint | Format | Max/page |
|---|---|---|---|---|---|
| www.dotandkey.com | Judge.me | `dot-key.myshopify.com` | judge.me reviews_for_widget | JSON | 30 |
| beminimalist.co | Yotpo | app key `Sphwk8Wj9Cg1x0FxDDivWxXcFjrv9ApHjy7kM0pR` | api-cdn.yotpo.com v1 / v3 | JSON | 150 (v1), 50+ (v3) |
| foxtale.in | Fera data via a Next.js server action (headless store) | n/a | POST foxtale.in (Next-Action) | RSC stream containing JSON | 100 |
| thedeconstruct.in | Judge.me | `thedeconstruct.myshopify.com` | judge.me reviews_for_widget | HTML inside JSON | 30 |
| thedermaco.com | Judge.me | `thedermaco.myshopify.com` | judge.me reviews_for_widget | HTML inside JSON | 30 |
| plumgoodness.com | Judge.me | `plumgoodness-2.myshopify.com` | judge.me reviews_for_widget | JSON | 30 |
| reequil.com | Nector | `ak_cc929cfb9abd57e3329c3a4a3261b3c01e3eabb1267b0346e6b3fb1ab14c1afd` | cachefront.nector.io | JSON | 100 |
| discoverpilgrim.com | Judge.me | `discoverpilgrim.myshopify.com` | judge.me reviews_for_widget | HTML inside JSON | 30 |
| aqualogica.in | Judge.me | `aqualogicaprod.myshopify.com` | judge.me reviews_for_widget | JSON | 30 |
| drsheths.com | Judge.me | `dr-sheths.myshopify.com` | judge.me reviews_for_widget | HTML inside JSON | 30 |
| fixderma.com | Judge.me | `fixderma-skincare.myshopify.com` | judge.me reviews_for_widget | JSON | 30 |

All 11 stores: `reviews_available: true`.

---

## 1. Judge.me (8 stores)

Stores: dotandkey, deconstruct, dermaco, plum, pilgrim, aqualogica, drsheths, fixderma.

**URL template**
```
https://judge.me/reviews/reviews_for_widget?url={shop}&shop_domain={shop}&platform=shopify&product_id={product_id}&page={page}&per_page={n}&sort_by=created_at&sort_dir=desc
```
- `{shop}` is the `*.myshopify.com` domain (the page's `Shopify.shop`).
- Plum's widget calls `https://cdn.judge.me/reviews/reviews_for_widget?...&widget_theme=standard`. That host returned 429 after a few calls, so prefer `judge.me`. Both return the same payload.
- Headers: browser User-Agent only.
- `per_page` is capped at **30** server-side. Asking for 50 or 100 still returns 30.
- `sort_dir=asc` also works. It returned the oldest review first on dotandkey.

The response shape depends on which widget the shop runs. You cannot choose it with a parameter.

### 1a. JSON mode: dotandkey, plum, aqualogica, fixderma

- Top level: `number_of_reviews`, `average_rating` (string), `histogram[] {rating, frequency, percentage}`, `pagination {total_pages, current_page, per_page}`.
- Reviews list: `reviews[]`.
  - id: `uuid`. The `id` field is absent.
  - rating: `rating` (int)
  - title: `title` (may be "")
  - body: `body_html` (HTML, e.g. `<p>…</p>`)
  - author: `reviewer_name`
  - date: `created_at` (ISO 8601)
  - verified: `verified_buyer` (bool)
  - also: `is_anonymous_reviewer`, `product_title`, `product_variant_title`, `pictures_urls`, `thumb_up`, `thumb_down`, `reply_content`, `location_country_code`
- **Pagination cap:** `total_pages` is capped at **33** (33 × 30 = 990 reviews). On dotandkey (1633 reviews), `page=34` returned page 33 again. To get older reviews, also page with `sort_dir=asc`, then dedupe on `uuid`.

### 1b. HTML mode: deconstruct, dermaco, pilgrim, drsheths

- Top level: `{html, total_count, page}`. There is no average and no total_pages, so compute pages as ceil(total_count / per_page).
- Each review is a `div.jdgm-rev` inside `html`:
  - id: attribute `data-review-id` (uuid)
  - verified: `data-verified-buyer='true'|'false'`
  - rating: `span.jdgm-rev__rating[data-score]`
  - date: `time.jdgm-rev__timestamp[datetime]`
  - author: `span.jdgm-rev__author` ("Anonymous" when anonymous)
  - title: `strong.jdgm-rev__title`
  - body: `div.jdgm-rev__body`
  - product: `data-product-title`, `data-product-url`
- Aggregate: there is no average in this response. The PDP's preview badge carries `.jdgm-prev-badge[data-average-rating][data-number-of-reviews]`.
- Last page returns fewer than per_page. Verified: deconstruct salicylic gel, page 9 × 30 → 15 reviews (total 255). The 990-review cap was not tested in HTML mode.

### Verified examples (judge.me)

| Store | Product (handle → id) | Result |
|---|---|---|
| dotandkey | watermelon-cooling-spf-50-face-sunscreen → 8152049385637 | JSON, 1633 total, avg 4.60, 30/page, pages capped at 33 |
| plum | green-tea-zinc-super-matte-spf-50-sunscreen-gel-for-oily-acne-prone-skin-30g → 8924254076988 | JSON, 423 total, avg 4.39, 15 pages |
| aqualogica | illuminate-dewy-sunscreen-spf-50-pa-with-wild-berries-alpha-arbutin-125-g → 8634637156577 | JSON, 87 total, avg 4.71 |
| fixderma | roll-on-sunscreen-for-face → 8076579012834 | JSON, 45 total, avg 4.78 (shadow-sunscreen-spf-30… → 5972622475458: 5) |
| deconstruct | salicylic-acid-gel-sunscreen → 10667195269401 | HTML, 255 total (gel-sunscreen-for-oily-skin-30gm → 15427857711385: only 4) |
| dermaco | 1-hyaluronic-sunscreen-aqua-gel-with-spf-50-pa-80g → 9791516082423 | HTML, 649 total (…oil-free-matte-gel-80-g → 9897544384759: 7) |
| pilgrim | 5-vitamin-c-complex-brightening-serum-sunscreen-spf-50-pa → 9417536995557 | HTML, 173 total (…super-light-gel-sunscreen-spf-50-pa-6 → 9472745242853: 42) |
| drsheths | centella-niacinamide-oil-free-matte-sunscreen-50g → 9439872057575 | HTML, 48 total (ceramide-vitamin-c-sunscreen-30g → 8805325209831: 2) |

Example URL:
```
https://judge.me/reviews/reviews_for_widget?url=dot-key.myshopify.com&shop_domain=dot-key.myshopify.com&platform=shopify&product_id=8152049385637&page=1&per_page=30&sort_by=created_at&sort_dir=desc
```

---

## 2. Yotpo: beminimalist.co

- App key: `Sphwk8Wj9Cg1x0FxDDivWxXcFjrv9ApHjy7kM0pR`. It is in the loader URL `cdn-widgetsrepository.yotpo.com/v1/loader/{appkey}`.
- Product id: Shopify product id. For example, light-fluid-spf-50-sunscreen → `7883925880993`.
- Headers: browser User-Agent only.

### v1 (recommended: largest pages, snake_case)
```
https://api-cdn.yotpo.com/v1/widget/{appkey}/products/{product_id}/reviews.json?per_page={n}&page={page}&sort=date
```
- Root: `response`
  - aggregate: `response.bottomline.average_score`, `response.bottomline.total_review`
  - pagination: `response.pagination {page, per_page, total}`
- Reviews list: `response.reviews[]`
  - id: `id` (int)
  - rating: `score`
  - title: `title`
  - body: `content`
  - author: `user.display_name`
  - date: `created_at`
  - verified: `verified_buyer`
  - also: `votes_up`, `votes_down`, `images_data`, `sentiment`, `comment` (store reply)
- `per_page=150` returned 150. Larger values were not tested.
- Verified: 431 total, avg 4.24.

### v3 (the endpoint the current widget calls)
```
https://api-cdn.yotpo.com/v3/storefront/store/{appkey}/product/{product_id}/reviews?page={page}&perPage={n}&sort=date
```
- Aggregate: `bottomline.totalReview`, `averageScore`, `starDistribution`.
- Pagination: `pagination {page, perPage, total}`.
- Reviews list: `reviews[]`
  - id: `id`
  - rating: `score`
  - title: `title`
  - body: `content`
  - author: `user.displayName`
  - date: `createdAt`
  - verified: `verifiedBuyer`
- perPage=50 was verified.

Example URL:
```
https://api-cdn.yotpo.com/v1/widget/Sphwk8Wj9Cg1x0FxDDivWxXcFjrv9ApHjy7kM0pR/products/7883925880993/reviews.json?per_page=150&page=1&sort=date
```
Note: the page also loads Nector (loyalty). The review widget is Yotpo.

---

## 3. Nector: reequil.com (www.reequil.com)

- The page also loads a Stamped script (`stamped.io/api/getappkey`), but the review list on the page is rendered by Nector (`#nector-reviews`).
- API key: public, from `#nector-reviews[data-api_key]` on the PDP: `ak_cc929cfb9abd57e3329c3a4a3261b3c01e3eabb1267b0346e6b3fb1ab14c1afd`.
- **Required headers:**
  - `x-apikey: {api_key}`
  - `x-source: web`
  - `accept: application/json`
  - `content-type: application/json`
  - Without `x-apikey` the API returns 401 "API credential is not valid".
```
https://cachefront.nector.io/api/v2/merchant/reviews?page={page}&limit={n}&sort=posted_at&sort_op=DESC&reference_product_id={product_id}&reference_product_source=shopify
```
- Root: `data`
  - total: `data.count`
  - aggregate: `data.stats[] {rating, count}`. There is no average field, so compute it.
  - also: `data.cursor {has_next, next_id, …}`
- Reviews list: `data.items[]`
  - id: `_id` (uuid)
  - rating: `rating` (**string**, e.g. "5")
  - title: none
  - body: `description`
  - author: `name`
  - date: `posted_at` (also `created_at`)
  - verified: `is_verified` (string "True"/"False" as returned)
  - also: `uploads`, `reference_product_name`
- Pagination: offset style with `page` + `limit`. page=2&limit=50 began exactly at item 50 of page=1&limit=100. `limit=100` was verified.
- Verified products:
  - oxybenzone-free-sunscreen-spf-50-for-oily-acne-prone-skin → 8356331421882: count 1821
  - ultra-matte-dry-touch-sunscreen-gel-spf-50-pa: 2841
  - zinc-mineral-tinted-sunscreen: 537
  - The task's handle, reequil-ultra-uv-hydrating-sunscreen → 8396806652090, has only 1 review.

Example URL (send the headers above):
```
https://cachefront.nector.io/api/v2/merchant/reviews?page=1&limit=100&sort=posted_at&sort_op=DESC&reference_product_id=8356331421882&reference_product_source=shopify
```

---

## 4. foxtale.in: headless Next.js, Fera-backed (fragile)

- The storefront is headless Next.js (`foxtale-consumer.myshopify.com` Storefront API). No Fera, Judge.me or other widget host is called from the browser. Reviews come from a **Next.js server action** named `getStoreReviews`. Its payload has Fera's review schema (`heading`, `body`, `is_verified`, `customer.generated_display_name`, `state`).
- The task's handle `matte-finish-sunscreen-spf-70` redirects to the homepage on the client. The live PDP is `/products/matte-finish-sunscreen` (Shopify id 7725413564663).
- **Request:**
  ```
  POST https://foxtale.in/products/{handle}
  Next-Action: 7f78a3fbae72e53c9a03f1e707e84a2103879974ac
  Accept: text/x-component
  Content-Type: text/plain;charset=UTF-8

  [{"productIds":"{comma-separated ids}","page":{page},"limit":{n}}]
  ```
- `productIds` must be the product's `reviews.grouped_product_ids` metafield, which is embedded in the server-rendered PDP HTML next to `reviews.avg_rating` and `reviews.total_reviews`. The main product id alone can return 0. For matte-finish-sunscreen:
  ```
  8259287089399,9498989789431,8296078606583,9598154014967,9866004070647,9903084732663,8270263288055,9962049044727,7725413564663
  ```
- **Response:** an RSC stream, not plain JSON. Row `1:` holds the JSON. Long strings are split into separate `N:T<hexlen>,<text>` rows and referenced as `"$N"`, so resolve those references. A working parser is at `/tmp/claude-502/reviews_probe/scripts/rsc.py`.
  - Pagination: `meta {page, page_size, total_count, page_count}`
  - Reviews list: `data[]`
    - id: `id` (uuid)
    - rating: `rating`
    - title: `heading` (also `subject`)
    - body: `body` (may be null)
    - author: `customer.generated_display_name` or `customer.name`
    - date: `created_at`
    - verified: `is_verified`
  - Aggregate: from the PDP metafields (`reviews.avg_rating` = 4.78, `reviews.total_reviews` = 858).
- Verified: total_count 858. limit=50 → 50 items, 18 pages. limit=100, page=2 → 100 items.
- **Fragility:** the `Next-Action` id changes when Foxtale redeploys. To find the new one, scan the `/_next/static/chunks/*.js` files loaded by the PDP for `createServerReference)("<hex>",…,"getStoreReviews")`. Found in chunk `21ej5rp56ncpy.js` on 2026-11-21.

---

## Not verified / caveats

- Judge.me HTML-mode pagination cap was not tested.
- The Yotpo v1 `per_page` limit above 150 was not tested.
- JSON-LD `aggregateRating` was not relied on. Each endpoint above returns its own aggregate (except Judge.me HTML mode and Nector's average).
- Scratch responses and helper scripts are in `/tmp/claude-502/reviews_probe/`.
