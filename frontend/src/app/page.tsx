import { Estimator } from "@/components/Estimator";

const STEPS = [
  {
    title: "The photo is read",
    text: "A vision model lists what it sees: which panel, what kind of damage and how bad.",
  },
  {
    title: "You check it",
    text: "Fix anything it got wrong. Prices update as you edit, without analysing the photo again.",
  },
  {
    title: "Rules set the price",
    text: "Labour hours, Ontario shop rates, parts and paint, the way body shop software does it.",
  },
];

export default function Home() {
  return (
    <Estimator
      intro={
        <div>
          <p className="eyebrow">Collision repair estimator</p>
          <h1 className="mt-3 text-4xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-5xl">
            What will the repair cost?
          </h1>
          <p className="mt-4 max-w-md text-[17px] leading-relaxed text-muted">
            Upload photos of the damage and get an itemized estimate in Canadian dollars, with every
            line explained.
          </p>
        </div>
      }
      outro={
        <section id="how-it-works" className="no-print scroll-mt-20">
          <h2 className="eyebrow">How it works</h2>
          <ol className="mt-3 border-t border-line">
            {STEPS.map((step, index) => (
              <li key={step.title} className="flex gap-4 border-b border-line py-4">
                <span className="w-6 shrink-0 pt-px font-mono text-sm text-muted">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <h3 className="font-semibold">{step.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      }
    />
  );
}
