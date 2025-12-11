import React from "react";
import {
  formatSimilarityScore,
  getDecisionBadgeClass,
  getDecisionLabel
} from "../../utils/formatters";

// 🔹 Stopwords list so we don't highlight common words
const stopwords = new Set([
  "the",
  "is",
  "are",
  "a",
  "an",
  "of",
  "in",
  "on",
  "to",
  "and",
  "or",
  "for",
  "with",
  "by",
  "as",
  "at",
  "from",
  "that",
  "this",
  "these",
  "those",
  "be",
  "was",
  "were",
  "it",
  "its",
  "into",
  "their",
  "there",
  "then"
]);

// 🔹 Helper to highlight overlap between question and syllabus chunk
function highlightOverlap(question, text) {
  if (!question || !text) return text;

  const questionWords = question
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((w) => w && !stopwords.has(w));

  const keySet = new Set(questionWords);

  // Split text but keep spaces
  const tokens = text.split(/(\s+)/);

  return tokens.map((tok, idx) => {
    const clean = tok.toLowerCase().replace(/[^a-z0-9]/g, "");
    if (clean && keySet.has(clean)) {
      return (
        <span key={idx} className="bg-yellow-200 font-semibold">
          {tok}
        </span>
      );
    }
    return <span key={idx}>{tok}</span>;
  });
}

function AnalysisResultPanel({ result }) {
  if (!result) {
    return (
      <div className="card bg-gray-50">
        <p className="text-gray-500 text-center">
          No results yet. Analyze a question to see the results here.
        </p>
      </div>
    );
  }

  const isBatch = Array.isArray(result.questions);

  // 🔹 Batch mode UI
  if (isBatch) {
    return (
      <div className="card">
        <h3 className="text-xl font-semibold mb-4">Batch Analysis Results</h3>

        <p className="text-sm text-gray-600 mb-4">
          Detected {result.questions.length} questions. Each card below shows
          whether that question is in syllabus and how strongly it matches.
        </p>

        <div className="space-y-4">
          {result.questions.map((qres, idx) => (
            <div
              key={idx}
              className="border border-gray-200 rounded-lg p-4 bg-gray-50"
            >
              {/* Question text */}
              <div className="mb-3">
                <h4 className="text-sm font-medium text-gray-700 mb-1">
                  Question {idx + 1}
                </h4>
                <p className="text-sm text-gray-900">{qres.question}</p>
              </div>

              {/* Decision badge */}
              <div className="mb-3">
                <div
                  className={`inline-flex items-center px-3 py-1 rounded-full border-2 text-xs font-semibold ${getDecisionBadgeClass(
                    qres.is_in_syllabus
                  )}`}
                >
                  {getDecisionLabel(qres.is_in_syllabus)}
                </div>
              </div>

              {/* Similarity */}
              <div className="mb-3">
                <h5 className="text-xs font-medium text-gray-700 mb-1">
                  Similarity Score
                </h5>
                <div className="flex items-center space-x-3">
                  <div className="flex-grow bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-gradient-to-r from-primary-500 to-accent-500 h-2 rounded-full transition-all duration-300"
                      style={{
                        width: `${(qres.similarity_score || 0) * 100}%`
                      }}
                    />
                  </div>
                  <span className="text-sm font-semibold text-gray-900">
                    {formatSimilarityScore(qres.similarity_score || 0)}%
                  </span>
                </div>
              </div>

              {/* Most relevant syllabus match */}
              {qres.top_chunks && qres.top_chunks.length > 0 && (
                <div>
                  <h5 className="text-xs font-medium text-gray-700 mb-1">
                    Most Relevant Syllabus Match
                  </h5>
                  <div className="p-3 bg-white rounded border border-gray-200">
                    <p className="text-sm text-gray-800 leading-relaxed">
                      {highlightOverlap(
                        qres.question,
                        qres.top_chunks[0].text
                      )}
                    </p>
                    {qres.top_chunks[0].distance !== undefined && (
                      <p className="text-xs text-gray-500 mt-2">
                        Distance: {qres.top_chunks[0].distance.toFixed(4)} |{" "}
                        Similarity:{" "}
                        {qres.top_chunks[0].similarity !== undefined
                          ? `${(
                              qres.top_chunks[0].similarity * 100
                            ).toFixed(1)}%`
                          : "—"}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // 🔹 Single-question UI (existing design)
  return (
    <div className="card">
      <h3 className="text-xl font-semibold mb-4">Analysis Results</h3>

      {/* Question that was analyzed */}
      {result.question && (
        <div className="mb-6">
          <h4 className="text-sm font-medium text-gray-700 mb-1">
            Question Analyzed
          </h4>
          <p className="text-gray-900 text-sm bg-gray-50 border border-gray-200 rounded-md p-3">
            {result.question}
          </p>
        </div>
      )}

      {/* Final Decision Badge */}
      <div className="mb-6">
        <div
          className={`inline-flex items-center px-4 py-2 rounded-full border-2 font-semibold ${getDecisionBadgeClass(
            result.is_in_syllabus
          )}`}
        >
          <span className="text-lg">
            {getDecisionLabel(result.is_in_syllabus)}
          </span>
        </div>
      </div>

      {/* Similarity Score */}
      <div className="mb-6">
        <h4 className="text-sm font-medium text-gray-700 mb-2">
          Similarity Score
        </h4>
        <div className="flex items-center space-x-4">
          <div className="flex-grow bg-gray-200 rounded-full h-3">
            <div
              className="bg-gradient-to-r from-primary-500 to-accent-500 h-3 rounded-full transition-all duration-300"
              style={{ width: `${(result.similarity_score || 0) * 100}%` }}
            />
          </div>
          <span className="text-lg font-semibold text-gray-900">
            {formatSimilarityScore(result.similarity_score || 0)}%
          </span>
        </div>
      </div>

      {/* Gatekeeper Status */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg">
        <h4 className="text-sm font-medium text-gray-700 mb-2">
          Cosine Gatekeeper
        </h4>
        <div className="flex items-center space-x-2">
          {result.gatekeeper_passed ? (
            <>
              <svg
                className="w-5 h-5 text-green-600"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="text-green-700 font-medium">
                Passed - LLM Validation Performed
              </span>
            </>
          ) : (
            <>
              <svg
                className="w-5 h-5 text-red-600"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="text-red-700 font-medium">
                Blocked - Below Threshold
              </span>
            </>
          )}
        </div>
      </div>

      {/* LLM Decision */}
      {result.llm_decision && (
        <div className="mb-6 p-4 bg-primary-50 rounded-lg border border-primary-200">
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            LLM Curriculum Validator
          </h4>
          <p className="text-gray-900 font-medium mb-2">
            Decision: {result.llm_decision}
          </p>
          <p className="text-gray-700 text-sm italic">
            {result.llm_justification}
          </p>
        </div>
      )}

      {/* Retrieved Syllabus Chunks */}
      {result.top_chunks && result.top_chunks.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-3">
            Most Relevant Syllabus Match
          </h4>
          <div className="space-y-3">
            {result.top_chunks.map((chunk, idx) => (
              <div
                key={idx}
                className="p-4 bg-gray-50 rounded-lg border border-gray-200"
              >
                {chunk.module && (
                  <p className="text-xs font-semibold text-primary-600 mb-1">
                    {chunk.module}
                  </p>
                )}
                <p className="text-sm text-gray-800 leading-relaxed">
                  {highlightOverlap(result.question, chunk.text)}
                </p>
                {chunk.distance !== undefined && (
                  <p className="text-xs text-gray-500 mt-2">
                    Distance: {chunk.distance.toFixed(4)} | Similarity:{" "}
                    {chunk.similarity !== undefined
                      ? `${(chunk.similarity * 100).toFixed(1)}%`
                      : "—"}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default AnalysisResultPanel;
