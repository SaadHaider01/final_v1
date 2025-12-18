export default function BatchSummary({ questions }) {
  const stats = { in: 0, borderline: 0, out: 0 };

  questions.forEach(q => {
    if (!q.gatekeeper_passed) stats.out++;
    else if (q.llm_decision === "YES") stats.in++;
    else stats.borderline++;
  });

  return (
    <div className="flex gap-6 p-4 bg-gray-100 rounded-lg mb-6">
      <span>✔ In Syllabus: {stats.in}</span>
      <span>⚠ Borderline: {stats.borderline}</span>
      <span>✖ Out: {stats.out}</span>
    </div>
  );
}
