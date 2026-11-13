# Cost data

How Crashtimate prices repairs, and where each number in
[`ontario.toml`](../backend/app/pricing/data/ontario.toml) comes from. Money is in CAD
before tax unless a row says otherwise.

## How an estimate is built

1. **Each damage gets an operation** ([rules.py](../backend/app/pricing/rules.py)):
   - Light scratches are buffed out.
   - Small dents get paintless dent repair.
   - Moderate damage is repaired in place, then the panel is repainted.
   - Severe damage means the part is replaced.
   - Glass, tires, wheels and sensor calibration go to specialists at flat ("sublet") prices.
2. **Damage on the same panel is combined.** The biggest job wins (a replacement absorbs a
   repair), and repairs on one panel add their hours together.
3. **Repainting** ([engine.py](../backend/app/pricing/engine.py)). Every repainted panel gets
   its refinish time. A panel painted next to another repainted panel gets 0.4 hours off,
   because the two share masking and setup. Untouched neighbouring panels are *blended* so
   the new paint fades into the old.
4. **Sensor calibration.** If the VIN shows the car has a lane camera, radar cruise control
   or blind-spot radar, work near that sensor adds a calibration charge. Without that data,
   the estimate adds a note instead.
5. **Pricing.** Labour hours are charged at the shop's hourly rates. Shop materials are
   charged per body hour and paint materials per paint hour. Parts and sublet work are
   added on top, then 13% HST.

Every amount is a range. The low end uses the lowest posted shop rates and aftermarket
parts; the high end uses the highest rates and dealer (OEM) parts.

## Labour and materials rates

Collision shops in Ontario post "door rates", meaning what they charge customers who pay
directly. These five set the ranges in `[rates.standard]` and `[rates.luxury]`:

| Shop | City | Rates dated | Body and refinish labour | Paint materials (per paint hour) | Shop materials (per body hour) | Luxury labour |
|---|---|---|---|---|---|---|
| [CSN Maple Leaf](https://csncollision.com/mapleleaf) | Niagara Falls | not dated | $85 | $48 ($60 luxury) | $12 ($20 luxury) | $125 |
| [CSN Emeryville](https://csncollision.com/locations/emeryville-collision-repair-centre-in-windsor) | Windsor | Oct 21, 2024 | $90 | $50 | $12 | not listed |
| [CSN Highland](https://csncollision.com/locations/highland-collision-repair-centre-in-ottawa/) | Ottawa | Nov 15, 2024 | $95 | $53 ($63 luxury) | $10 ($15 luxury) | $125 |
| [AWIN Advanced Auto Body](https://www.awin.ca/awin-advanced-auto-body-centre.html) | North York, Toronto | not dated | $95 | not listed | not listed | $100 (Mercedes-Benz, Jaguar, Land Rover, luxury EVs) |
| [CSN RSK Downtown](https://csncollision.com/locations/csn-rsk-downtown) | Hamilton | Feb 17, 2025 | $105 | $50 | $15 | $135 |

| | Standard vehicles | Luxury vehicles |
|---|---|---|
| Body and refinish labour | $85–$105 per hour | $100–$135 per hour |
| Paint materials | $48–$53 per paint hour | $60–$63 per paint hour |
| Shop materials | $10–$15 per body hour | $15–$20 per body hour |

## Parts

Part prices are set for a mainstream car, using the 2019 Honda Civic sedan as a reference.
The low end is a certified aftermarket part and the high end a dealer part. Where only US
prices were found, they're converted at 1.38 CAD per USD.

| Part | Cost book | Evidence |
|---|---|---|
| Bumper cover | $250–$750 | Certified aftermarket cover: $341–$476 at [Central Alberta Paint Supply](https://centralalbertapaintsupply.ca/?p=547469). Primed aftermarket cover: US$120 at [Painted Auto Parts](https://paintedautoparts.com/honda-civic-sedan-front-bumper-cover-primed-exc-si-usa-capa-oem-04711tbaa50zz-2019-2021-pl-ho1000322c.html). |
| Hood | $300–$1,100 | Dealer hood: US$525 (list US$782) at [Honda Parts Now](https://hondapartsnow.com/oem-2019-honda-civic-hood.html), about $725–$1,080. The low end is an assumption for an aftermarket hood. |
| Front fender | $120–$350 | Dealer fender: US$124 (list US$181) at [Honda Parts Now](https://hondapartsnow.com/oem-2019-honda-civic-fender.html). The range is widened for other models. |
| Mirror | $120–$800 | Dealer mirror assemblies: US$397 to US$601 at [Honda Parts Connection](https://www.hondapartsconnection.com/v-2019-honda-civic--lx--1-5l-l4-gas/body--outside-mirrors). |
| Headlight | $200–$1,200 | [Synchrony](https://www.synchrony.com/blog/automotive/headlight-replacement-cost) (US, Sep 2025): most assemblies cost "several hundred dollars"; LED units cost $600 to nearly $3,000. |
| Doors, trunk lid, quarter panel, roof, rocker, grille, taillight, wheel | see the file | Assumptions. |

## Labour hours

The major estimating databases (Mitchell, CCC, Audatex) are licensed, so the hours in the
cost book are assumptions. They're checked by the calibration tests below.

- **Refinish time per panel** (hood 3.0 h, front door 2.6 h, fender 2.2 h, bumper cover 2.8
  h, and so on) is an assumption in line with the
  [ari.app labour-times guide](https://ari.app/2026/07/auto-body-labor-times-estimating-guide/),
  whose worked example uses 3.0 hours for a hood or fender.
- **Overlap deduction:** 0.4 hours for a panel next to another repainted panel, following the
  same guide.
- **Blend:** 50–100% of the neighbouring panel's refinish time. The three major estimating
  systems allow 50%. An SCRS study found blending took 31.59% *longer* than a full refinish
  ([FenderBender, Nov 2022](https://fenderbender.com/news/article/55052063/society-of-collision-repair-specialists-scrs-time-required-to-blend-is-greater-than-full-refinish-scrs-study-finds)),
  so the high end charges the full refinish time.
- **Repair hours** (by panel size and severity), **polish hours** and **replace hours** are
  assumptions. Replacement hours for welded panels (quarter panel, rocker, roof) are much
  higher because the old panel is cut out and the new one welded in.

## Specialist (sublet) prices

| Job | Cost book | Evidence |
|---|---|---|
| Paintless dent repair | $75–$400, by panel size | $75–$300 per dent, and up to $750–$850 for larger jobs ([experts.ca](https://experts.ca/resources/auto-services/auto-body-shop-cost-canada), May 2026) |
| Windshield replacement | $300–$800 | $300–$600 in Ontario ([Auto Glass Dixie](https://www.autoglassdixie.com/windshield-glass/the-true-cost-of-windshield-replacement-in-ontario-and-how-to-save)); $400–$800 ([isure.ca](https://isure.ca/?p=36296)) |
| Sensor calibration | $200–$500 | $200–$400 for windshield cameras (both sources above). The high end allows for bumper radar. |
| Tire repair | $30–$60 | [tireset.ca](https://www.tireset.ca/blog/article/when-to-patch-plug-repair-a-tire-a-complete-guide-for-canadian-drivers) |
| Tire replacement | $150–$330 | $20–$40 to mount and balance ([experts.ca](https://experts.ca/resources/auto-services/tire-change-cost-canada)) plus a $130–$290 tire (assumption) |
| Curb rash repair, rim straightening | $100–$200, $100–$250 | General price guides, plus one Vancouver report of about $150 ([REVscene](https://www.revscene.net/forums/588382-unintentionally-damaged-my-wheel-when-i-tried-remove-%3B-how-much-fix.html)). Weak evidence. |
| Rear and side glass, chip repair, lens restoration, mirror glass | see the file | Assumptions |

## Vehicle adjustments

- **Luxury vehicles** use the shops' posted luxury rates.
  - Parts cost 2× (assumption).
  - Lamps cost 3×. This is set so a luxury headlight lands within
    [Ontario owners' quotes](https://www.collisionrepairmag.com/news/collision-repair/article/15723308/glaring-costs-headlight-repair-costs-too-high-say-two-ontario-drivers):
    $2,000 for one headlight, over $3,500 for a Mercedes headlight, and $7,400 for a pair on
    a Tesla Model S.
  - Which makes count as luxury is an assumption.
- **SUVs and trucks** have bigger panels. Their parts and paint time are multiplied by 1.15
  and 1.25 (assumption).
- **The VIN** is decoded with NHTSA's free [vPIC API](https://vpic.nhtsa.dot.gov/api/). It
  gives the make (for the luxury tier), the body class (for size) and the driver-assist
  features (for calibration).

## Tax

Ontario HST is 13%
([Canada Revenue Agency](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/charge-collect-which-rate.html)).

## Calibration checks

[`test_pricing_calibration.py`](../backend/tests/test_pricing_calibration.py) prices common
repairs and checks that the middle of each estimate (before tax) falls inside a published
range:

| Repair | Estimate | Published | Source |
|---|---|---|---|
| Door ding, paintless repair | $125–$300 | $75–$300 | experts.ca |
| Windshield with lane-camera calibration | $500–$1,300 | $500–$1,400 | Auto Glass Dixie, isure.ca |
| Mainstream headlight | $248–$1,440 | $414–$1,380 (US$300–$1,000) | Synchrony |
| Luxury headlight | $658–$3,910 | $2,000–$3,700 | Collision Repair Magazine |
| Front bumper cover replacement | $812–$1,613 | $1,104–$3,450 (US$800–$2,500) | [Northwest Auto Collision](https://www.northwestautocollision.com/how-much-does-a-car-bumper-repair-cost/), Dec 2025 |

When a cost-book number changes, these tests show whether estimates still match the real
world.

## Known gaps

- **One region.** Rates come from Ontario shops. A postal code elsewhere adds a note but
  doesn't change prices.
- **No licensed labour times.** Hours are reasoned assumptions, not figures from Mitchell,
  CCC or Audatex.
- **Exterior only.** Frame, structural, mechanical and airbag damage aren't priced; the
  disclaimer on every estimate says so.
- **Four-door body assumed** when deciding which panels to blend.
- **Simple calibration rules.** Lane cameras are tied to the windshield, front radar to the
  front bumper and grille, and blind-spot radar to the rear bumper. Real vehicles vary.
- **Mixed source quality.** Shop rate sheets are primary data. Most consumer price guides are
  secondary, and several are US-based. Both are used only to set and check ranges.
