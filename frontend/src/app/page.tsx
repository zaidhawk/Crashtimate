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
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            What will the repair cost?
          </h1>
          <p className="mt-3 text-muted">
            Upload photos of the damage and get an itemized estimate in Canadian dollars, with every
            line explained.
          </p>
        </div>
      }
      outro={
        <ol className="no-print mx-auto grid max-w-4xl gap-4 sm:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="card p-4">
              <p className="text-xs font-semibold text-accent">STEP {index + 1}</p>
              <h2 className="mt-1 font-semibold">{step.title}</h2>
              <p className="mt-1 text-sm text-muted">{step.text}</p>
            </li>
          ))}
        </ol>
      }
    />
  );
}
