import { groupByPanel } from "@/lib/estimate";
import { formatCost, formatHours, vehicleName } from "@/lib/format";
import { DAMAGE_TYPE_LABELS, OPERATION_LABELS, panelLabel } from "@/lib/labels";
import type { CostRange, Estimate, EstimateLine, Operation } from "@/lib/types";

const OPERATION_STYLES: Record<Operation, string> = {
  replace: "bg-red-50 text-red-800",
  repair: "bg-orange-50 text-orange-800",
  paintless_repair: "bg-amber-50 text-amber-800",
  polish: "bg-amber-50 text-amber-800",
  refinish: "bg-sky-50 text-sky-800",
  blend: "bg-sky-50 text-sky-800",
  calibrate: "bg-violet-50 text-violet-800",
};

/** What a line is made of, e.g. "1.5 – 3.0 h body · parts $180 – $420". */
function lineDetail(line: EstimateLine): string {
  const parts: string[] = [];
  if (line.body_hours) parts.push(`${formatHours(line.body_hours)} body`);
  if (line.refinish_hours) parts.push(`${formatHours(line.refinish_hours)} paint`);
  if (line.parts) parts.push(`parts ${formatCost(line.parts)}`);
  if (line.sublet) parts.push("specialist, flat price");
  return parts.join(" · ");
}

export function EstimateHeadline({ estimate }: { estimate: Estimate }) {
  const name = vehicleName(estimate.vehicle);
  return (
    <div>
      <p className="text-sm font-medium text-muted">Estimated repair cost</p>
      <p className="mt-1 text-4xl font-semibold tracking-tight tabular-nums sm:text-5xl">
        {formatCost(estimate.totals.total)}
      </p>
      <p className="mt-2 text-sm text-muted">
        {estimate.currency}, including {estimate.tax_name} · {estimate.region} shop rates
        {name ? ` · ${name}` : ""}
      </p>
    </div>
  );
}

export function EstimateTable({ estimate }: { estimate: Estimate }) {
  const groups = groupByPanel(estimate.lines);
  if (groups.length === 0) {
    return <p className="text-sm text-muted">Nothing to price.</p>;
  }
  return (
    <div className="divide-y divide-line">
      {groups.map((group) => (
        <section key={group.panel} className="py-4 first:pt-0 last:pb-0">
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="font-semibold">{panelLabel(group.panel)}</h3>
            <p className="text-sm font-semibold whitespace-nowrap tabular-nums">
              {formatCost(group.cost)}
            </p>
          </div>
          <ul className="mt-2 space-y-2">
            {group.lines.map((line, index) => (
              <li key={index} className="flex items-start justify-between gap-4 text-sm">
                <div className="min-w-0">
                  <span
                    className={`mr-2 inline-block rounded px-1.5 py-0.5 text-xs font-medium ${OPERATION_STYLES[line.operation]}`}
                  >
                    {OPERATION_LABELS[line.operation]}
                  </span>
                  <span>{line.description}</span>
                  <p className="mt-0.5 text-xs text-muted">{lineDetail(line)}</p>
                </div>
                <p className="whitespace-nowrap text-muted tabular-nums">{formatCost(line.cost)}</p>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function TotalRow({ label, cost, strong }: { label: string; cost: CostRange; strong?: boolean }) {
  if (!strong && cost.high === 0) return null;
  return (
    <div
      className={`flex justify-between gap-4 ${strong ? "font-semibold text-ink" : "text-muted"}`}
    >
      <dt>{label}</dt>
      <dd className="whitespace-nowrap tabular-nums">{formatCost(cost)}</dd>
    </div>
  );
}

export function EstimateTotals({ estimate }: { estimate: Estimate }) {
  const { totals, hourly_rates: rates } = estimate;
  return (
    <div>
      <dl className="space-y-1.5 text-sm">
        <TotalRow
          label={`Body labour (${formatHours(totals.body_hours)})`}
          cost={totals.body_labour}
        />
        <TotalRow label="Shop materials" cost={totals.shop_materials} />
        <TotalRow
          label={`Paint labour (${formatHours(totals.refinish_hours)})`}
          cost={totals.refinish_labour}
        />
        <TotalRow label="Paint materials" cost={totals.paint_materials} />
        <TotalRow label="Parts" cost={totals.parts} />
        <TotalRow label="Specialist work" cost={totals.sublet} />
        <div className="my-2 border-t border-line" />
        <TotalRow label="Subtotal" cost={totals.subtotal} strong />
        <TotalRow label={estimate.tax_name} cost={totals.tax} />
        <div className="my-2 border-t border-line" />
        <div className="text-base">
          <TotalRow label="Total" cost={totals.total} strong />
        </div>
      </dl>
      <p className="hint">
        Rates used: body labour {formatCost(rates.body_labour)}/h, paint labour{" "}
        {formatCost(rates.refinish_labour)}/h. The low end assumes aftermarket parts and lower shop
        rates; the high end dealer parts and higher rates.
      </p>
    </div>
  );
}

export function EstimateNotes({ estimate }: { estimate: Estimate }) {
  return (
    <div className="space-y-4">
      {estimate.unpriced.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm">
          <h3 className="font-semibold text-amber-900">Not included in the price</h3>
          <ul className="mt-2 space-y-1.5 text-amber-900">
            {estimate.unpriced.map((item, index) => (
              <li key={index}>
                <span className="font-medium">
                  {DAMAGE_TYPE_LABELS[item.damage_type]} on the{" "}
                  {panelLabel(item.panel).toLowerCase()}:
                </span>{" "}
                {item.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
      <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted">
        {estimate.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </div>
  );
}
