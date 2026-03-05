import React, { useState, useMemo } from 'react';
import { useApiClient } from '../../hooks/useApiClient';
import {
  getBosOptions,
  getDeptOptions,
  getProgramOptions,
  getSemesterOptions,
} from '../../config/makautData';

/**
 * QuestionForm — Upgrade A
 *
 * Cascading SELECTs from static MAKAUT data:
 *   BOS → Department → Program → Semester → Subject (from ingested syllabi)
 *
 * The final Subject dropdown is filtered from syllabusOptions (live data)
 * using the selections made in the first 4 static dropdowns.
 */
function QuestionForm({ onResult, syllabusOptions = [] }) {
  const { analyzeQuestion, loading } = useApiClient();

  const [inputMode, setInputMode] = useState('text');
  const [question, setQuestion] = useState('');
  const [pdfFile, setPdfFile] = useState(null);
  const [threshold, setThreshold] = useState(0.2);
  const [error, setError] = useState(null);

  // Cascade state
  const [bos, setBos] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [selectedProgram, setSelectedProgram] = useState('');
  const [selectedSemester, setSelectedSemester] = useState('');
  const [selectedSyllabusId, setSelectedSyllabusId] = useState('');

  // ── Static cascade options ────────────────────────────────────────────────

  const bosOptions = useMemo(() => getBosOptions(), []);
  const deptOptions = useMemo(() => getDeptOptions(bos), [bos]);
  const programOptions = useMemo(() => getProgramOptions(bos, selectedDepartment), [bos, selectedDepartment]);
  const semOptions = useMemo(() => getSemesterOptions(bos, selectedDepartment, selectedProgram), [bos, selectedDepartment, selectedProgram]);

  // Filter live syllabi by the static selections
  const filteredSyllabi = useMemo(() =>
    syllabusOptions.filter(s =>
      (!bos || s.bos === bos) &&
      (!selectedDepartment || s.department === selectedDepartment) &&
      (!selectedProgram || s.program === selectedProgram) &&
      (!selectedSemester || s.semester === selectedSemester)
    ),
    [syllabusOptions, bos, selectedDepartment, selectedProgram, selectedSemester]);

  // Reset downstream
  const handleBos = v => { setBos(v); setSelectedDepartment(''); setSelectedProgram(''); setSelectedSemester(''); setSelectedSyllabusId(''); };
  const handleDept = v => { setSelectedDepartment(v); setSelectedProgram(''); setSelectedSemester(''); setSelectedSyllabusId(''); };
  const handleProgram = v => { setSelectedProgram(v); setSelectedSemester(''); setSelectedSyllabusId(''); };
  const handleSem = v => { setSelectedSemester(v); setSelectedSyllabusId(''); };

  // ── Submit ────────────────────────────────────────────────────────────────

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!selectedSyllabusId) { setError('Please select a subject'); return; }
    if (inputMode === 'text' && !question.trim()) { setError('Please enter a question'); return; }
    if (inputMode === 'pdf' && !pdfFile) { setError('Please upload a PDF'); return; }

    try {
      let result;
      if (inputMode === 'text') {
        result = await analyzeQuestion({
          mode: 'text',
          question: question.trim(),
          syllabus_id: selectedSyllabusId,
          threshold,
        });
      } else {
        const fd = new FormData();
        fd.append('mode', 'pdf');
        fd.append('file', pdfFile);
        fd.append('syllabus_id', selectedSyllabusId);
        fd.append('threshold', threshold.toString());
        result = await analyzeQuestion(fd);
      }
      onResult(result);
    } catch (err) {
      setError(err.message || 'Something went wrong');
    }
  };

  const CascadeSelect = ({ id, label, value, onChange, options, locked }) => (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-gray-600 mb-1">
        {label}
        {locked && <span className="text-gray-400 font-normal ml-2">— select above first</span>}
      </label>
      <select
        id={id}
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={locked}
        className={`input-field text-sm ${locked ? 'opacity-40 cursor-not-allowed bg-gray-100' : ''}`}
      >
        <option value="">— {label} —</option>
        {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
      </select>
    </div>
  );

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="card">
      <h3 className="text-xl font-semibold mb-4">Analyze Question</h3>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">

        {/* Input Mode */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Input Mode</label>
          <div className="flex gap-3">
            {[['text', 'Type Question'], ['pdf', 'Upload PDF']].map(([m, lbl]) => (
              <button key={m} type="button" onClick={() => setInputMode(m)}
                className={`px-4 py-2 rounded-lg border font-medium text-sm ${inputMode === m
                    ? 'bg-primary-100 border-primary-500 text-primary-700'
                    : 'bg-gray-50 border-gray-300 text-gray-700'
                  }`}>
                {lbl}
              </button>
            ))}
          </div>
        </div>

        {/* ── Cascading Syllabus Selection ── */}
        <div className="space-y-3 border border-indigo-100 rounded-xl p-4 bg-indigo-50/40">
          <p className="text-xs font-semibold text-indigo-700 uppercase tracking-wide">
            🎓 Select Syllabus
          </p>

          <CascadeSelect id="q-bos" label="University / BOS" value={bos} onChange={handleBos} options={bosOptions} locked={false} />
          <CascadeSelect id="q-department" label="Department" value={selectedDepartment} onChange={handleDept} options={deptOptions} locked={!bos} />
          <CascadeSelect id="q-program" label="Program" value={selectedProgram} onChange={handleProgram} options={programOptions} locked={!selectedDepartment} />
          <CascadeSelect id="q-semester" label="Semester" value={selectedSemester} onChange={handleSem} options={semOptions} locked={!selectedProgram} />

          {/* Subject — filtered live syllabi */}
          <div>
            <label htmlFor="q-subject" className="block text-xs font-medium text-gray-600 mb-1">
              Subject *
              {selectedSemester && filteredSyllabi.length === 0 && (
                <span className="text-amber-600 font-normal ml-2">— no syllabi ingested for this selection yet</span>
              )}
            </label>
            <select
              id="q-subject"
              value={selectedSyllabusId}
              onChange={e => setSelectedSyllabusId(e.target.value)}
              disabled={!selectedSemester || filteredSyllabi.length === 0}
              required
              className={`input-field text-sm ${!selectedSemester || filteredSyllabi.length === 0
                  ? 'opacity-40 cursor-not-allowed bg-gray-100'
                  : ''
                }`}
            >
              <option value="">— Select Subject —</option>
              {filteredSyllabi.map(s => (
                <option key={s.syllabus_id} value={s.syllabus_id}>
                  {s.subject_name} ({s.subject_code})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Threshold */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Similarity Threshold: <span className="font-bold">{threshold.toFixed(2)}</span>
          </label>
          <input type="range" min="0" max="1" step="0.05" value={threshold}
            onChange={e => setThreshold(parseFloat(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600" />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>0.00 (Lenient)</span>
            <span>1.00 (Strict)</span>
          </div>
        </div>

        {/* Question Input */}
        {inputMode === 'text' ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Exam Question *</label>
            <textarea value={question} onChange={e => setQuestion(e.target.value)}
              placeholder="Enter the exam question to analyze..." rows={4}
              className="input-field" required />
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Question PDF *</label>
            <input type="file" accept=".pdf" onChange={e => setPdfFile(e.target.files[0])} className="w-full" required />
            {pdfFile && <p className="mt-2 text-sm text-gray-600">Selected: {pdfFile.name}</p>}
          </div>
        )}

        <button type="submit"
          disabled={loading || !selectedSyllabusId}
          className="btn-primary w-full">
          {loading ? 'Analyzing...' : 'Analyze Question'}
        </button>
      </form>
    </div>
  );
}

export default QuestionForm;
