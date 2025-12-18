import { useState } from "react";
import VerdictBadge from "./VerdictBadge";
import SimilarityBar from "./SimilarityBar";

function deriveVerdict(q) {
  if (!q.gatekeeper_passed) return "out";
  if (q.llm_decision === "YES") return "in";
  if (q.similarity_score >= 0.6) return "borderline";
  return "out";
}

export default function QuestionCard({ data, index }) {
  const [open, setOpen] = useState(false);
  const verdict = deriveVerdict(data);

  return (
    <div className="border rounded-lg p-4 shadow-sm bg-white">
      <div
        className="flex justify-between items-start cursor-pointer"
        onClick={() => setOpen(!open)}
      >
        <div>
          <h3 className="font-semibold text-gray-800">
            Q{index + 1}. {data.question}
          </h3>
          <div className="mt-2">
            <VerdictBadge verdict={verdict} />
          </div>
        </div>
        <span className="text-gray-500">{open ? "▲" : "▼"}</span>
      </div>

      <SimilarityBar score={data.similarity_score} />

      {open && (
        <div className="mt-4 text-sm space-y-3 text-gray-700">
          <p className="italic">
            {data.llm_justification || "No validator explanation available."}
          </p>

          {data.top_chunks?.length > 0 && (
            <div>
              <strong>Most Relevant Syllabus Evidence:</strong>
              <div className="mt-1 bg-gray-50 p-2 rounded">
                {data.top_chunks[0].text}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
