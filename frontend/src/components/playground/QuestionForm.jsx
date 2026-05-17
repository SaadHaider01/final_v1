import React, { useState, useMemo } from 'react';
import { useApiClient } from '../../hooks/useApiClient';

/**
 * QuestionForm — Curriculum-Driven Version
 *
 * Hierarchy: Department → Semester → Subject
 * All options derived dynamically from syllabusOptions (backend SYLLABI data).
 * No static BOS/Program dropdowns — those are removed.
 *
 * Sends ONLY { question, syllabus_id } to /analyze_question.
 * Department/Semester/Subject are already internally mapped via syllabus_id.
 */
function QuestionForm({ onResult, syllabusOptions = [] }) {
  const { analyzeQuestion, detectSubject, loading } = useApiClient();

  const [inputMode, setInputMode]   = useState('text');
  const [question, setQuestion]     = useState('');
  const [pdfFile, setPdfFile]       = useState(null);
  const [threshold, setThreshold]   = useState(0.8);
  const [error, setError]           = useState(null);

  // Cascade state — curriculum-driven (no BOS/Program)
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [selectedSemester, setSelectedSemester]     = useState('');
  const [selectedSyllabusId, setSelectedSyllabusId] = useState('');

  // ── Dynamic cascade options derived from syllabusOptions ─────────────────

  const deptOptions = useMemo(() =>
    [...new Set(syllabusOptions.map(s => (s.curriculum_department || s.department || "Department Unknown")))].sort()
  , [syllabusOptions]);

  const semOptions = useMemo(() =>
    [...new Set(syllabusOptions
      .filter(s => {
        const d = (s.curriculum_department || s.department || "Department Unknown");
        return !selectedDepartment || d === selectedDepartment;
      })
      .map(s => s.semester).filter(Boolean))].sort()
  , [syllabusOptions, selectedDepartment]);

  const filteredSyllabi = useMemo(() =>
    syllabusOptions.filter(s => {
      const d = (s.curriculum_department || s.department || "Department Unknown");
      return (!selectedDepartment || d === selectedDepartment) &&
             (!selectedSemester   || s.semester === selectedSemester);
    })
  , [syllabusOptions, selectedDepartment, selectedSemester]);

  // Reset/sync downstream on cascade change
  const handleDept = v => { setSelectedDepartment(v); setSelectedSemester(''); setSelectedSyllabusId(''); };
  const handleSem  = v => { setSelectedSemester(v); setSelectedSyllabusId(''); };
  const handleSubject = sid => {
    setSelectedSyllabusId(sid);
    if (sid) {
      const match = syllabusOptions.find(s => s.syllabus_id === sid);
      if (match) {
        // Step 1: Auto-sync hierarchy
        const targetDept = (match.curriculum_department || match.department || "Department Unknown");
        if (selectedDepartment !== targetDept) setSelectedDepartment(targetDept);
        if (match.semester && selectedSemester !== match.semester) setSelectedSemester(match.semester);
      }
    }
  };

  // ── Auto-Detect ──────────────────────────────────────────────────────────
  const handleAutoDetect = async () => {
    if (inputMode === 'text' && !question.trim()) { setError('Please enter a question to auto-detect'); return; }
    if (inputMode === 'pdf'  && !pdfFile)         { setError('Please upload a PDF to auto-detect'); return; }

    setError(null);
    try {
      let payload;
      if (inputMode === 'text') {
        payload = { mode: 'text', text: question.trim() };
      } else {
        payload = new FormData();
        payload.append('mode', 'pdf');
        payload.append('file', pdfFile);
      }

      const res = await detectSubject(payload);
      if (res.success && res.metadata) {
        const { syllabus_id: mSid, department: mDept, semester: mSem, subject_code: mCode } = res.metadata;
        let foundSomething = false;

        // 1. Try exact syllabus_id match (new semantic detection)
        if (mSid && syllabusOptions.find(s => s.syllabus_id === mSid)) {
          handleSubject(mSid);
          foundSomething = true;
        } 
        // 2. Fallback to code-based matching
        else if (mCode) {
          const match = syllabusOptions.find(s => s.subject_code === mCode);
          if (match) {
            handleSubject(match.syllabus_id);
            foundSomething = true;
          }
        }
        
        // 3. Metadata fragments (dept/sem)
        if (!foundSomething) {
          if (mDept) { setSelectedDepartment(mDept); foundSomething = true; }
          if (mSem)  { setSelectedSemester(mSem);    foundSomething = true; }
        }

        if (!foundSomething) {
          setError('Could not detect a matching subject. Please select manually.');
        }
      }
    } catch (err) {
      setError(err.message || 'Detection failed');
    }
  };

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!selectedSyllabusId)            { setError('Please select a subject');      return; }
    if (inputMode === 'text' && !question.trim()) { setError('Please enter a question'); return; }
    if (inputMode === 'pdf'  && !pdfFile)         { setError('Please upload a PDF');     return; }

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

  // ── Helper: cascade select ─────────────────────────────────────────────────
  const CascadeSelect = ({ id, label, value, onChange, options, locked }) => (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-gray-600 mb-1">
        {label}
        {locked && <span className="text-gray-400 font-normal ml-2">— select above first</span>}
      </label>
      <select id={id} value={value} onChange={e => onChange(e.target.value)} disabled={locked}
        className={`input-field text-sm ${locked ? 'opacity-40 cursor-not-allowed bg-gray-100' : ''}`}>
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
                  : 'bg-gray-50 border-gray-300 text-gray-700'}`}>
                {lbl}
              </button>
            ))}
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
            <input type="file" accept=".pdf,.docx,.pptx" onChange={e => setPdfFile(e.target.files[0])} className="w-full" required />
            {pdfFile && <p className="mt-2 text-sm text-gray-600">Selected: {pdfFile.name}</p>}
          </div>
        )}

        {/* ── Curriculum-Driven Subject Selection ── */}
        <div className="space-y-3 border border-indigo-100 rounded-xl p-4 bg-indigo-50/40">
          <div className="flex justify-between items-center">
            <p className="text-xs font-semibold text-indigo-700 uppercase tracking-wide">
              🎓 Select Subject (from ingested curriculum)
            </p>
            <button type="button" onClick={handleAutoDetect} disabled={loading}
              className="text-xs bg-indigo-100 text-indigo-700 hover:bg-indigo-200 px-2 py-1 rounded font-medium transition-colors">
              🪄 Detect Matching Subject
            </button>
          </div>

          {syllabusOptions.length === 0 ? (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
              ⚠️ No syllabi ingested yet. Upload a curriculum PDF first (Tab 1).
            </div>
          ) : (
            <>
              {/* Department */}
              <CascadeSelect
                id="q-department" label="Department"
                value={selectedDepartment} onChange={handleDept}
                options={deptOptions} locked={false} />

              {/* Semester */}
              <CascadeSelect
                id="q-semester" label="Semester"
                value={selectedSemester} onChange={handleSem}
                options={semOptions} locked={!selectedDepartment} />

              {/* Subject */}
              <div>
                <label htmlFor="q-subject" className="block text-xs font-medium text-gray-600 mb-1">
                  Subject *
                  {selectedSemester && filteredSyllabi.length === 0 && (
                    <span className="text-amber-600 font-normal ml-2">— no syllabi for this selection</span>
                  )}
                </label>
                <select id="q-subject" value={selectedSyllabusId} onChange={e => handleSubject(e.target.value)}
                  disabled={filteredSyllabi.length === 0} required
                  className={`input-field text-sm ${filteredSyllabi.length === 0 ? 'opacity-40 cursor-not-allowed bg-gray-100' : ''}`}>
                  <option value="">— Select Subject —</option>
                  {filteredSyllabi.map(s => (
                    <option key={s.syllabus_id} value={s.syllabus_id}>
                      {s.subject_name}{s.subject_code ? ` (${s.subject_code})` : ''}
                      {s.elective_type && s.elective_type !== 'CORE' ? ` [${s.elective_type}]` : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Show selected subject summary */}
              {selectedSyllabusId && (() => {
                const sel = syllabusOptions.find(s => s.syllabus_id === selectedSyllabusId);
                return sel ? (
                  <div className="text-xs text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg p-3 mt-4 shadow-sm">
                    <p className="font-semibold text-indigo-800 mb-1.5 uppercase tracking-wider text-[10px]">Retrieval Scope:</p>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-bold text-primary-700 bg-primary-50 px-1.5 py-0.5 rounded border border-primary-200">
                        {sel.program || "Program Unknown"}
                      </span>
                      <span className="text-indigo-300">→</span>
                      <span className="font-medium bg-white px-1.5 py-0.5 rounded border border-indigo-100">
                        {sel.curriculum_department || sel.department || "Department Unknown"}
                      </span>
                      <span className="text-indigo-300">→</span>
                      <span className="font-medium bg-white px-1.5 py-0.5 rounded border border-indigo-100">Semester {sel.semester || "?"}</span>
                      <span className="text-indigo-300">→</span>
                      <span className="font-bold text-indigo-900 bg-indigo-100 border border-indigo-300 px-1.5 py-0.5 rounded">
                        {sel.subject_name} {sel.subject_code ? `(${sel.subject_code})` : ''}
                      </span>
                    </div>
                  </div>
                ) : null;
              })()}
            </>
          )}
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

        <button type="submit" disabled={loading || !selectedSyllabusId} className="btn-primary w-full">
          {loading ? 'Analyzing...' : 'Analyze Question'}
        </button>
      </form>
    </div>
  );
}

export default QuestionForm;
