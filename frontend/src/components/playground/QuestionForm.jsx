import React, { useState, useEffect } from 'react';
import { useApiClient } from '../../hooks/useApiClient';

function QuestionForm({ onResult, syllabusOptions = [] }) {
  const { analyzeQuestion, loading } = useApiClient();

  const [inputMode, setInputMode] = useState('text'); // 'text' or 'pdf'
  const [question, setQuestion] = useState('');
  const [pdfFile, setPdfFile] = useState(null);
  const [selectedSyllabus, setSelectedSyllabus] = useState('');
  const [threshold, setThreshold] = useState(0.2);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (syllabusOptions.length > 0 && !selectedSyllabus) {
      setSelectedSyllabus(syllabusOptions[0].syllabus_id);
    }
  }, [syllabusOptions, selectedSyllabus]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!selectedSyllabus) {
      setError('Please select a syllabus or ingest one first');
      return;
    }

    if (inputMode === 'text' && !question.trim()) {
      setError('Please enter a question');
      return;
    }

    if (inputMode === 'pdf' && !pdfFile) {
      setError('Please upload a question PDF');
      return;
    }

    try {
      let result;

      if (inputMode === 'text') {
        // Existing JSON-based flow
        result = await analyzeQuestion({
          mode: 'text',
          question: question.trim(),
          syllabus_id: selectedSyllabus,
          threshold,
        });
      } else {
        // New PDF-based flow using FormData
        const formData = new FormData();
        formData.append('mode', 'pdf');
        formData.append('file', pdfFile);
        formData.append('syllabus_id', selectedSyllabus);
        formData.append('threshold', threshold.toString());

        result = await analyzeQuestion(formData);
      }

      onResult(result);
    } catch (err) {
      setError(err.message || 'Something went wrong while analyzing the question');
    }
  };

  return (
    <div className="card">
      <h3 className="text-xl font-semibold mb-4">Analyze Question</h3>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Input Mode Toggle */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Input Mode
          </label>
          <div className="flex space-x-4">
            <button
              type="button"
              onClick={() => setInputMode('text')}
              className={`px-4 py-2 rounded-lg border font-medium ${
                inputMode === 'text'
                  ? 'bg-primary-100 border-primary-500 text-primary-700'
                  : 'bg-gray-50 border-gray-300 text-gray-700'
              }`}
            >
              Type Question
            </button>
            <button
              type="button"
              onClick={() => setInputMode('pdf')}
              className={`px-4 py-2 rounded-lg border font-medium ${
                inputMode === 'pdf'
                  ? 'bg-primary-100 border-primary-500 text-primary-700'
                  : 'bg-gray-50 border-gray-300 text-gray-700'
              }`}
            >
              Upload Question PDF
            </button>
          </div>
        </div>

        {/* Syllabus Selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Select Syllabus *
          </label>
          {syllabusOptions.length === 0 ? (
            <p className="text-sm text-gray-500 italic">
              No syllabi available. Please ingest a syllabus first.
            </p>
          ) : (
            <select
              value={selectedSyllabus}
              onChange={(e) => setSelectedSyllabus(e.target.value)}
              className="input-field"
              required
            >
              {syllabusOptions.map((syllabus) => (
                <option key={syllabus.syllabus_id} value={syllabus.syllabus_id}>
                  {syllabus.department} - {syllabus.program} - Sem {syllabus.semester} - {syllabus.subject_name}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Threshold Slider */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Similarity Threshold: {threshold.toFixed(2)}
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>0.00 (Lenient)</span>
            <span>1.00 (Strict)</span>
          </div>
        </div>

        {/* Question Input OR PDF Upload */}
        {inputMode === 'text' ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Exam Question *
            </label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Enter the exam question to analyze..."
              rows={4}
              className="input-field"
              required
            />
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Question PDF *
            </label>
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setPdfFile(e.target.files[0])}
              className="w-full"
              required
            />
            {pdfFile && (
              <p className="mt-2 text-sm text-gray-600">
                Selected: {pdfFile.name}
              </p>
            )}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || syllabusOptions.length === 0}
          className="btn-primary w-full"
        >
          {loading ? 'Analyzing...' : 'Analyze Question'}
        </button>
      </form>
    </div>
  );
}

export default QuestionForm;
