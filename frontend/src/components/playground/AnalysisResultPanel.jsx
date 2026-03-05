import React from "react";
import {
  formatSimilarityScore,
  getDecisionBadgeClass,
  getDecisionLabel
} from "../../utils/formatters";

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Remove duplicate chunks by text content */
function dedupChunks(chunks = []) {
  const seen = new Set();
  return chunks.filter(c => {
    const key = (c.text || "").trim();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

const stopwords = new Set([
  "the", "is", "are", "a", "an", "of", "in", "on", "to", "and", "or",
  "for", "with", "by", "as", "at", "from", "that", "this", "these",
  "those", "be", "was", "were", "it", "its", "into", "their", "there", "then"
]);

function highlightOverlap(question, text) {
  if (!question || !text) return text;
  const qWords = question.toLowerCase().split(/[^a-z0-9]+/).filter(w => w && !stopwords.has(w));
  const keySet = new Set(qWords);
  return text.split(/(\s+)/).map((tok, idx) => {
    const clean = tok.toLowerCase().replace(/[^a-z0-9]/g, "");
    return clean && keySet.has(clean)
      ? <span key={idx} className="bg-yellow-200 font-semibold">{tok}</span>
      : <span key={idx}>{tok}</span>;
  });
}

// Bloom level → colour class
const BLOOM_COLOR = {
  Remember: "bg-sky-100 text-sky-800 border-sky-300",
  Understand: "bg-blue-100 text-blue-800 border-blue-300",
  Apply: "bg-green-100 text-green-800 border-green-300",
  Analyze: "bg-yellow-100 text-yellow-800 border-yellow-300",
  Evaluate: "bg-orange-100 text-orange-800 border-orange-300",
  Create: "bg-purple-100 text-purple-800 border-purple-300",
  Unknown: "bg-gray-100 text-gray-600 border-gray-300",
};

const DIFFICULTY_COLOR = {
  Easy: "bg-green-50 text-green-700 border-green-300",
  Medium: "bg-yellow-50 text-yellow-700 border-yellow-300",
  Hard: "bg-red-50 text-red-700 border-red-300",
  Unknown: "bg-gray-50 text-gray-500 border-gray-300",
};

function Badge({ label, colorClass, prefix }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-semibold ${colorClass}`}>
      {prefix && <span className="opacity-60">{prefix}</span>}
      {label}
    </span>
  );
}

// ─── Curriculum Analysis row (Bloom + Difficulty + Modules + CO + PCO) ────────

function EnrichmentRow({ result }) {
  if (!result) return null;

  const bloom = result.bloom_level || "Unknown";
  const difficulty = result.difficulty || "Unknown";
  const modules = result.modules_detected;
  const co = result.mapped_co;
  const pco = result.mapped_pco;

  return (
    <div className="mb-4 p-4 bg-indigo-50 border border-indigo-200 rounded-lg space-y-3">
      <h4 className="text-sm font-semibold text-indigo-900">Curriculum Analysis</h4>

      <div className="flex flex-wrap gap-2 items-center">
        {/* Bloom — always shown */}
        <Badge label={bloom} colorClass={BLOOM_COLOR[bloom] || BLOOM_COLOR.Unknown} prefix="Bloom:" />

        {/* Difficulty — always shown */}
        <Badge label={difficulty} colorClass={DIFFICULTY_COLOR[difficulty] || DIFFICULTY_COLOR.Unknown} prefix="Difficulty:" />

        {/* CO */}
        {co && <Badge label={co} colorClass="bg-violet-100 text-violet-800 border-violet-300" prefix="CO:" />}

        {/* PCO */}
        {pco && <Badge label={pco} colorClass="bg-teal-100 text-teal-800 border-teal-300" prefix="PO:" />}
      </div>

      {/* Unknown bloom hint */}
      {bloom === "Unknown" && (
        <p className="text-xs text-gray-500 italic">
          Bloom level could not be detected — no recognisable action verb found in the question.
        </p>
      )}

      {/* Modules detected */}
      {modules && modules.length > 0 && (
        <div>
          <p className="text-xs font-medium text-indigo-700 mb-1">Modules Detected</p>
          <div className="flex flex-wrap gap-2">
            {modules.map((mod, i) => (
              <span
                key={i}
                className="inline-block px-2 py-0.5 bg-indigo-100 text-indigo-800 border border-indigo-300 rounded text-xs font-medium"
              >
                {mod}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Chunk list (shared by batch and single) ──────────────────────────────────

function ChunkList({ question, chunks, compact = false }) {
  const deduped = dedupChunks(chunks);
  if (deduped.length === 0) return null;

  return (
    <div>
      <h5 className={`font-medium text-gray-700 mb-2 ${compact ? "text-xs" : "text-sm"}`}>
        Most Relevant Syllabus Match{deduped.length > 1 ? "es" : ""}
      </h5>
      <div className="space-y-2">
        {deduped.map((chunk, i) => (
          <div key={i} className={`bg-white rounded border border-gray-200 ${compact ? "p-3" : "p-4 bg-gray-50 rounded-lg"}`}>
            {chunk.module && (
              <p className="text-xs font-semibold text-primary-600 mb-1">{chunk.module}</p>
            )}
            <p className={`text-gray-800 leading-relaxed ${compact ? "text-sm" : "text-sm"}`}>
              {highlightOverlap(question, chunk.text)}
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
  );
}

// ─── Batch card ──────────────────────────────────────────────────────────────

function BatchCard({ qres, idx }) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
      {/* Question */}
      <div className="mb-3">
        <h4 className="text-sm font-medium text-gray-700 mb-1">Question {idx + 1}</h4>
        <p className="text-sm text-gray-900">{qres.question}</p>
      </div>

      {/* Decision badge */}
      <div className="mb-3">
        <div className={`inline-flex items-center px-3 py-1 rounded-full border-2 text-xs font-semibold ${getDecisionBadgeClass(qres.is_in_syllabus)}`}>
          {getDecisionLabel(qres.is_in_syllabus)}
        </div>
      </div>

      {/* Similarity */}
      <div className="mb-3">
        <h5 className="text-xs font-medium text-gray-700 mb-1">Similarity Score</h5>
        <div className="flex items-center space-x-3">
          <div className="flex-grow bg-gray-200 rounded-full h-2">
            <div
              className="bg-gradient-to-r from-primary-500 to-accent-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(qres.similarity_score || 0) * 100}%` }}
            />
          </div>
          <span className="text-sm font-semibold text-gray-900">
            {formatSimilarityScore(qres.similarity_score || 0)}%
          </span>
        </div>
      </div>

      {/* Curriculum enrichment */}
      <EnrichmentRow result={qres} />

      {/* LLM Decision */}
      {qres.llm_decision && (
        <div className="mb-3 p-3 bg-primary-50 rounded-lg border border-primary-200">
          <h5 className="text-xs font-medium text-gray-700 mb-1">LLM Curriculum Validator</h5>
          <p className="text-sm text-gray-900 font-medium">Decision: {qres.llm_decision}</p>
          {qres.llm_justification && (
            <p className="text-xs text-gray-700 mt-1 italic">{qres.llm_justification}</p>
          )}
          {qres.llm_module && qres.llm_module.toLowerCase() !== "unknown" && (
            <p className="text-xs text-gray-600 mt-1">
              <strong>Module Match:</strong> {qres.llm_module}
            </p>
          )}
        </div>
      )}

      {/* Top chunks — deduplicated */}
      {qres.top_chunks && qres.top_chunks.length > 0 && (
        <ChunkList question={qres.question} chunks={qres.top_chunks} compact />
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

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

  // BATCH MODE
  if (result.mode === "batch" || Array.isArray(result.questions)) {
    return (
      <div className="card">
        <h3 className="text-xl font-semibold mb-4">Batch Analysis Results</h3>
        <p className="text-sm text-gray-600 mb-4">
          Detected {result.questions.length} questions.
        </p>
        <div className="space-y-4">
          {result.questions.map((qres, idx) => (
            <BatchCard key={idx} qres={qres} idx={idx} />
          ))}
        </div>
      </div>
    );
  }

  // SINGLE MODE
  return (
    <div className="card">
      <h3 className="text-xl font-semibold mb-4">Analysis Results</h3>

      {/* Question */}
      {result.question && (
        <div className="mb-6">
          <h4 className="text-sm font-medium text-gray-700 mb-1">Question Analyzed</h4>
          <p className="text-gray-900 text-sm bg-gray-50 border border-gray-200 rounded-md p-3">
            {result.question}
          </p>
        </div>
      )}

      {/* Final Decision Badge */}
      <div className="mb-6">
        <div className={`inline-flex items-center px-4 py-2 rounded-full border-2 font-semibold ${getDecisionBadgeClass(result.is_in_syllabus)}`}>
          <span className="text-lg">{getDecisionLabel(result.is_in_syllabus)}</span>
        </div>
      </div>

      {/* Similarity Score */}
      <div className="mb-6">
        <h4 className="text-sm font-medium text-gray-700 mb-2">Similarity Score</h4>
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
      {result.gatekeeper_passed !== undefined && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Cosine Gatekeeper</h4>
          <div className="flex items-center space-x-2">
            {result.gatekeeper_passed ? (
              <>
                <svg className="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span className="text-green-700 font-medium">Passed — LLM Validation Performed</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                <span className="text-red-700 font-medium">Blocked — Below Threshold</span>
              </>
            )}
          </div>
        </div>
      )}

      {/* Curriculum Enrichment Panel */}
      <EnrichmentRow result={result} />

      {/* LLM Decision */}
      {result.llm_decision && (
        <div className="mb-6 p-4 bg-primary-50 rounded-lg border border-primary-200">
          <h4 className="text-sm font-medium text-gray-700 mb-2">LLM Curriculum Validator</h4>
          <p className="text-gray-900 font-medium mb-2">Decision: {result.llm_decision}</p>
          {result.llm_justification && (
            <p className="text-gray-700 text-sm italic mb-2">{result.llm_justification}</p>
          )}
          {result.llm_module && result.llm_module.toLowerCase() !== "unknown" && (
            <p className="text-gray-700 text-sm">
              <strong>Module Match:</strong> {result.llm_module}
            </p>
          )}
        </div>
      )}

      {/* Retrieved Syllabus Chunks — deduplicated */}
      {result.top_chunks && result.top_chunks.length > 0 && (
        <ChunkList question={result.question} chunks={result.top_chunks} />
      )}
    </div>
  );
}

export default AnalysisResultPanel;