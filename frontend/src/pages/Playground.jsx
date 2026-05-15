import React, { useState, useEffect } from 'react';
import SectionHeader from '../components/common/SectionHeader';
import SyllabusUploadForm from '../components/playground/SyllabusUploadForm';
import QuestionForm from '../components/playground/QuestionForm';
import AnalysisResultPanel from '../components/playground/AnalysisResultPanel';
import { useApiClient } from '../hooks/useApiClient';

function Playground() {
  const { listSyllabi, deleteSyllabus, purgeAll } = useApiClient();
  const [syllabusOptions, setSyllabusOptions] = useState([]);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [activeTab, setActiveTab] = useState('upload');

  // Load syllabi on mount
  useEffect(() => {
    loadSyllabi();
  }, []);

  const loadSyllabi = async () => {
    try {
      const data = await listSyllabi();
      setSyllabusOptions(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to load syllabi:', error);
    }
  };

  const handleSyllabusSuccess = (result) => {
    loadSyllabi();
    setActiveTab('analyze');
  };

  const handleDeleteSyllabus = async (syllabusId) => {
    if (!window.confirm('Are you sure you want to delete this syllabus?')) return;
    try {
      await deleteSyllabus(syllabusId);
      loadSyllabi();
    } catch (error) {
      alert('Failed to delete syllabus: ' + error.message);
    }
  };

  const handlePurgeAll = async () => {
    if (!window.confirm('WARNING: This will delete ALL syllabi and vector records. Are you sure?')) return;
    try {
      await purgeAll();
      loadSyllabi();
      setAnalysisResult(null);
    } catch (error) {
      alert('Failed to purge data: ' + error.message);
    }
  };

  const handleAnalysisResult = (result) => {
    setAnalysisResult(result);
  };

  return (
    <div className="section-container">
      <SectionHeader
        title="Interactive Demo"
        subtitle="Try the RAG-based syllabus analyzer with your own syllabi and questions"
      />

      <div className="max-w-7xl mx-auto">
        {/* Instructions */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
          <h3 className="font-semibold text-blue-900 mb-2">How to Use</h3>
          <ol className="list-decimal list-inside space-y-1 text-blue-800 text-sm">
            <li>First, ingest a syllabus by uploading a PDF or pasting text</li>
            <li>Then, enter a question and select which syllabus to analyze against</li>
            <li>Adjust the similarity threshold to control gatekeeper behavior</li>
            <li>Click "Analyze Question" to see the system's decision and reasoning</li>
          </ol>
        </div>

        {/* Tab Navigation */}
        <div className="mb-6 border-b border-gray-200">
          <div className="flex space-x-1">
            <button
              onClick={() => setActiveTab('upload')}
              className={`px-6 py-3 font-medium text-sm border-b-2 transition-colors ${
                activeTab === 'upload'
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              1. Ingest Syllabus
            </button>
            <button
              onClick={() => setActiveTab('analyze')}
              className={`px-6 py-3 font-medium text-sm border-b-2 transition-colors ${
                activeTab === 'analyze'
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              2. Analyze Question
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Column - Forms */}
          <div>
            {activeTab === 'upload' ? (
              <SyllabusUploadForm onSuccess={handleSyllabusSuccess} />
            ) : (
              <QuestionForm 
                onResult={handleAnalysisResult} 
                syllabusOptions={syllabusOptions}
              />
            )}

            {/* Syllabus List */}
            {syllabusOptions.length > 0 && (
              <div className="card mt-6">
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-lg font-semibold">Available Syllabi ({syllabusOptions.length})</h3>
                  <button 
                    onClick={handlePurgeAll}
                    className="text-xs font-medium text-red-600 hover:text-red-800 bg-red-50 px-2 py-1 rounded border border-red-100 transition-colors"
                  >
                    Purge All
                  </button>
                </div>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {syllabusOptions.map((syllabus) => (
                    <div
                      key={syllabus.syllabus_id}
                      className="p-3 bg-gray-50 rounded border border-gray-200 text-sm flex justify-between items-start group"
                    >
                      <div>
                        <div className="font-medium text-gray-900">{syllabus.subject_name}</div>
                        <div className="text-xs text-gray-600 mt-1">
                          {syllabus.department} • {syllabus.program} • Semester {syllabus.semester}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          ID: {syllabus.syllabus_id.substring(0, 8)}...
                        </div>
                      </div>
                      <button 
                        onClick={() => handleDeleteSyllabus(syllabus.syllabus_id)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-600 transition-all"
                        title="Delete Syllabus"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Results */}
          <div>
            <AnalysisResultPanel result={analysisResult} />
          </div>
        </div>

        {/* Example Questions */}
        <div className="mt-12 card bg-gray-50">
          <h3 className="text-xl font-semibold mb-4">Example Test Scenarios</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-white rounded-lg border border-green-300">
              <div className="text-sm font-semibold text-green-700 mb-2">✓ In-Syllabus Example</div>
              <p className="text-xs text-gray-700 italic">
                "Explain the time complexity of merge sort algorithm"
                <br/><span className="text-gray-500">(if syllabus contains merge sort)</span>
              </p>
            </div>
            <div className="p-4 bg-white rounded-lg border border-yellow-300">
              <div className="text-sm font-semibold text-yellow-700 mb-2">⚠ Semantically Related</div>
              <p className="text-xs text-gray-700 italic">
                "Discuss Timsort optimization techniques"
                <br/><span className="text-gray-500">(if syllabus has merge sort but not Timsort)</span>
              </p>
            </div>
            <div className="p-4 bg-white rounded-lg border border-red-300">
              <div className="text-sm font-semibold text-red-700 mb-2">✗ Keyword Trap</div>
              <p className="text-xs text-gray-700 italic">
                "How do arrays work in stock market trading?"
                <br/><span className="text-gray-500">(keyword 'array' but different domain)</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Playground;
