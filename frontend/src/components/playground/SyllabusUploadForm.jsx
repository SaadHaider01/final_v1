import React, { useState } from 'react';
import { useApiClient } from '../../hooks/useApiClient';

function SyllabusUploadForm({ onSuccess }) {
  const { ingestSyllabus, loading } = useApiClient();
  const [inputMode, setInputMode] = useState('pdf'); // 'pdf' or 'text'
  const [pdfFile, setPdfFile] = useState(null);
  const [syllabusText, setSyllabusText] = useState('');
  const [metadata, setMetadata] = useState({
    department: '',
    program: '',
    semester: '',
    subject_code: '',
    subject_name: '',
  });
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    // Validation
    if (!metadata.department || !metadata.program || !metadata.semester || !metadata.subject_code || !metadata.subject_name) {
      setError('Please fill in all metadata fields');
      return;
    }

    if (inputMode === 'pdf' && !pdfFile) {
      setError('Please select a PDF file');
      return;
    }

    if (inputMode === 'text' && !syllabusText.trim()) {
      setError('Please enter syllabus content');
      return;
    }

    const formData = new FormData();
    formData.append('mode', inputMode);
    formData.append('department', metadata.department);
    formData.append('program', metadata.program);
    formData.append('semester', metadata.semester);
    formData.append('subject_code', metadata.subject_code);
    formData.append('subject_name', metadata.subject_name);

    if (inputMode === 'pdf') {
      formData.append('file', pdfFile);
    } else {
      formData.append('text', syllabusText);
    }

    try {
      const result = await ingestSyllabus(formData);
      setSuccess(`Syllabus ingested successfully! ID: ${result.syllabus_id}`);
      if (onSuccess) onSuccess(result);
      
      // Reset form
      setPdfFile(null);
      setSyllabusText('');
      setMetadata({
        department: '',
        program: '',
        semester: '',
        subject_code: '',
        subject_name: '',
      });
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="card">
      <h3 className="text-xl font-semibold mb-4">Ingest Syllabus</h3>
      
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
          {error}
        </div>
      )}
      
      {success && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 text-green-700 rounded-lg">
          {success}
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
              onClick={() => setInputMode('pdf')}
              className={`px-4 py-2 rounded-lg border font-medium ${
                inputMode === 'pdf'
                  ? 'bg-primary-100 border-primary-500 text-primary-700'
                  : 'bg-gray-50 border-gray-300 text-gray-700'
              }`}
            >
              Upload PDF
            </button>
            <button
              type="button"
              onClick={() => setInputMode('text')}
              className={`px-4 py-2 rounded-lg border font-medium ${
                inputMode === 'text'
                  ? 'bg-primary-100 border-primary-500 text-primary-700'
                  : 'bg-gray-50 border-gray-300 text-gray-700'
              }`}
            >
              Paste Text
            </button>
          </div>
        </div>

        {/* Metadata Fields */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Department *
            </label>
            <input
              type="text"
              value={metadata.department}
              onChange={(e) => setMetadata({ ...metadata, department: e.target.value })}
              placeholder="e.g., Information Technology"
              className="input-field"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Program *
            </label>
            <input
              type="text"
              value={metadata.program}
              onChange={(e) => setMetadata({ ...metadata, program: e.target.value })}
              placeholder="e.g., B.Tech IT"
              className="input-field"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Semester *
            </label>
            <input
              type="text"
              value={metadata.semester}
              onChange={(e) => setMetadata({ ...metadata, semester: e.target.value })}
              placeholder="e.g., 5"
              className="input-field"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Subject Code *
            </label>
            <input
              type="text"
              value={metadata.subject_code}
              onChange={(e) => setMetadata({ ...metadata, subject_code: e.target.value })}
              placeholder="e.g., IT301"
              className="input-field"
              required
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Subject Name *
            </label>
            <input
              type="text"
              value={metadata.subject_name}
              onChange={(e) => setMetadata({ ...metadata, subject_name: e.target.value })}
              placeholder="e.g., Data Structures"
              className="input-field"
              required
            />
          </div>
        </div>

        {/* PDF Upload or Text Input */}
        {inputMode === 'pdf' ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Syllabus PDF *
            </label>
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setPdfFile(e.target.files[0])}
              className="w-full"
              required
            />
            {pdfFile && (
              <p className="mt-2 text-sm text-gray-600">Selected: {pdfFile.name}</p>
            )}
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Syllabus Content *
            </label>
            <textarea
              value={syllabusText}
              onChange={(e) => setSyllabusText(e.target.value)}
              placeholder="Paste syllabus text here..."
              rows={8}
              className="input-field font-mono text-sm"
              required
            />
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="btn-primary w-full"
        >
          {loading ? 'Ingesting...' : 'Ingest Syllabus'}
        </button>
      </form>
    </div>
  );
}

export default SyllabusUploadForm;
