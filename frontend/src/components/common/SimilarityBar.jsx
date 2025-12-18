export default function SimilarityBar({ score }) {
  let color = "bg-red-500";
  let label = "Weak";

  if (score >= 0.8) {
    color = "bg-green-500";
    label = "Strong";
  } else if (score >= 0.6) {
    color = "bg-yellow-500";
    label = "Moderate";
  }

  return (
    <div className="mt-3">
      <div className="flex justify-between text-xs mb-1 text-gray-600">
        <span>Semantic Similarity</span>
        <span>{label} ({Math.round(score * 100)}%)</span>
      </div>
      <div className="w-full bg-gray-200 rounded h-2">
        <div
          className={`${color} h-2 rounded`}
          style={{ width: `${score * 100}%` }}
        />
      </div>
    </div>
  );
}
