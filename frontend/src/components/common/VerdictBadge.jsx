export default function VerdictBadge({ verdict }) {
  const styles = {
    in: "bg-green-100 text-green-800",
    borderline: "bg-yellow-100 text-yellow-800",
    out: "bg-red-100 text-red-800",
  };

  const labels = {
    in: "IN SYLLABUS",
    borderline: "BORDERLINE",
    out: "OUT OF SYLLABUS",
  };

  return (
    <span
      className={`px-3 py-1 rounded-full text-xs font-semibold ${styles[verdict]}`}
    >
      {labels[verdict]}
    </span>
  );
}
