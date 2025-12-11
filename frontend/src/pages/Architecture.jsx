import React from 'react';
import SectionHeader from '../components/common/SectionHeader';
import Card from '../components/common/Card';

function Architecture() {
  return (
    <div className="section-container">
      <SectionHeader
        title="System Architecture"
        subtitle="A two-stage RAG pipeline combining vector similarity with LLM intelligence"
      />

      <div className="max-w-6xl mx-auto space-y-12">
        {/* Architecture Overview */}
        <Card>
          <h3 className="text-2xl font-semibold mb-6">Architecture Overview</h3>
          
          {/* Stage 1: Offline Ingestion */}
          <div className="mb-8">
            <h4 className="text-xl font-semibold text-primary-700 mb-4">Stage 1: Offline Syllabus Ingestion</h4>
            <div className="bg-gray-50 p-6 rounded-lg border-2 border-gray-200">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-300 h-full flex flex-col justify-center">
                    <div className="text-3xl mb-2">📄</div>
                    <div className="font-semibold text-sm">PDF/Text Input</div>
                  </div>
                </div>
                <div className="flex items-center justify-center">
                  <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
                <div className="text-center">
                  <div className="bg-white p-4 rounded-lg shadow-sm border border-primary-300 h-full flex flex-col justify-center">
                    <div className="text-3xl mb-2">✂️</div>
                    <div className="font-semibold text-sm">Regex Chunking</div>
                    <div className="text-xs text-gray-600 mt-1">Modules/Units</div>
                  </div>
                </div>
                <div className="flex items-center justify-center">
                  <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-4">
                <div className="text-center md:col-start-2">
                  <div className="bg-white p-4 rounded-lg shadow-sm border border-accent-300 h-full flex flex-col justify-center">
                    <div className="text-3xl mb-2">🧠</div>
                    <div className="font-semibold text-sm">SBERT Embedding</div>
                    <div className="text-xs text-gray-600 mt-1">Dense Vectors</div>
                  </div>
                </div>
                <div className="flex items-center justify-center">
                  <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
                <div className="text-center">
                  <div className="bg-white p-4 rounded-lg shadow-sm border border-green-300 h-full flex flex-col justify-center">
                    <div className="text-3xl mb-2">💾</div>
                    <div className="font-semibold text-sm">Vector Store</div>
                    <div className="text-xs text-gray-600 mt-1">ChromaDB</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Stage 2: Runtime Analysis */}
          <div>
            <h4 className="text-xl font-semibold text-accent-700 mb-4">Stage 2: Runtime Question Analysis</h4>
            <div className="bg-gray-50 p-6 rounded-lg border-2 border-gray-200">
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                <div className="text-center">
                  <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-300 h-full flex flex-col justify-center">
                    <div className="text-3xl mb-2">❓</div>
                    <div className="font-semibold text-sm">Question Input</div>
                  </div>
                </div>
                <div className="flex items-center justify-center">
                  <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
                <div className="text-center">
                  <div className="bg-white p-4 rounded-lg shadow-sm border border-primary-300 h-full flex flex-col justify-center">
                    <div className="text-3xl mb-2">🔍</div>
                    <div className="font-semibold text-sm">Vector Search</div>
                    <div className="text-xs text-gray-600 mt-1">Top-k Retrieval</div>
                  </div>
                </div>
                <div className="flex items-center justify-center">
                  <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
                <div className="text-center">
                  <div className="bg-white p-4 rounded-lg shadow-sm border border-yellow-300 h-full flex flex-col justify-center">
                    <div className="text-3xl mb-2">🚧</div>
                    <div className="font-semibold text-sm">Cosine Gatekeeper</div>
                    <div className="text-xs text-gray-600 mt-1">Threshold Filter</div>
                  </div>
                </div>
              </div>
              <div className="flex justify-center mt-6">
                <div className="text-center max-w-xs">
                  <div className="bg-gradient-to-r from-accent-100 to-accent-200 p-4 rounded-lg shadow-md border-2 border-accent-400">
                    <div className="text-3xl mb-2">🤖</div>
                    <div className="font-semibold text-sm">LLM Curriculum Validator</div>
                    <div className="text-xs text-gray-700 mt-1">Few-Shot Decision</div>
                  </div>
                  <div className="mt-3 text-sm text-gray-600">
                    (Only if gatekeeper passed)
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Component Details */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <h4 className="text-lg font-semibold text-primary-700 mb-3">Sentence-BERT (SBERT)</h4>
            <p className="text-gray-700 text-sm leading-relaxed">
              SBERT generates dense semantic embeddings for both syllabus chunks and questions. Unlike traditional 
              word embeddings, SBERT captures sentence-level meaning, enabling accurate semantic similarity 
              measurement. The model is downloaded locally for offline operation.
            </p>
          </Card>

          <Card>
            <h4 className="text-lg font-semibold text-primary-700 mb-3">ChromaDB Vector Store</h4>
            <p className="text-gray-700 text-sm leading-relaxed">
              ChromaDB provides efficient storage and retrieval of high-dimensional embeddings. It uses approximate 
              nearest neighbor (ANN) search with cosine distance to quickly find the most similar syllabus chunks 
              for any given question.
            </p>
          </Card>

          <Card>
            <h4 className="text-lg font-semibold text-yellow-700 mb-3">Cosine Gatekeeper</h4>
            <p className="text-gray-700 text-sm leading-relaxed mb-2">
              The gatekeeper converts vector distance to similarity (similarity = 1 − distance) and applies a 
              configurable threshold. Questions below the threshold are immediately rejected without LLM processing, 
              significantly reducing computational costs.
            </p>
            <div className="bg-yellow-50 p-3 rounded border border-yellow-200 text-xs">
              <strong>Impact:</strong> Reduces LLM calls by ~70% while maintaining accuracy
            </div>
          </Card>

          <Card>
            <h4 className="text-lg font-semibold text-accent-700 mb-3">LLM Curriculum Validator</h4>
            <p className="text-gray-700 text-sm leading-relaxed mb-2">
              A local LLM acts as the final judge, using few-shot prompting with dynamic, domain-agnostic examples. 
              It distinguishes between in-syllabus questions, semantically related but out-of-scope questions, and 
              keyword traps.
            </p>
            <div className="bg-accent-50 p-3 rounded border border-accent-200 text-xs">
              <strong>Example Rule:</strong> If syllabus mentions Algorithm A but not Algorithm B, questions about 
              only Algorithm B are out-of-scope
            </div>
          </Card>
        </div>

        {/* Key Design Decisions */}
        <Card className="bg-gradient-to-br from-primary-50 to-accent-50 border-primary-200">
          <h3 className="text-2xl font-semibold mb-4">Key Design Decisions</h3>
          <div className="space-y-4">
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">Regex-Based Structural Chunking</h4>
              <p className="text-gray-700 text-sm">
                Instead of arbitrary fixed-size chunks, we use regex patterns to identify natural syllabus boundaries 
                (modules, units, chapters), preserving semantic coherence and improving retrieval quality.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">Two-Stage Filtering</h4>
              <p className="text-gray-700 text-sm">
                The gatekeeper + LLM architecture balances cost and accuracy: fast vector search eliminates obvious 
                mismatches, while the LLM handles nuanced cases requiring deeper understanding.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">Dynamic Few-Shot Prompting</h4>
              <p className="text-gray-700 text-sm">
                Rather than hard-coding examples for specific subjects, the system generates or templates examples 
                from the current syllabus, making it truly domain-agnostic and scalable to any discipline.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">Local-First Architecture</h4>
              <p className="text-gray-700 text-sm">
                All models (SBERT, LLM) are downloaded and run locally, ensuring data privacy, offline operation, 
                and eliminating API costs and latency.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default Architecture;
