import React, { useState, useMemo } from 'react';
import { useApiClient } from '../../hooks/useApiClient';
import {
  getBosOptions,
  getDeptOptions,
  getProgramOptions,
  getSemesterOptions,
} from '../../config/makautData';

/**
 * SyllabusUploadForm
 *
 * Layout:
 * ┌────────────────────────────────────────────────────────┐
 * │  SECTION 1 — Academic Metadata (fill ONCE, persists)   │
 * │   BOS → Department → Program → Semester                │
 * │   (stays after submit so you can upload multiple subs) │
 * ├────────────────────────────────────────────────────────┤
 * │  SECTION 2 — Subject Content (per upload)              │
 * │   Subject Code + Name                                  │
 * │   COs + PCOs  ← per-subject, inside this section       │
 * │   [PDF]  [Paste Text]  [From URL]                      │
 * └────────────────────────────────────────────────────────┘
 */
function SyllabusUploadForm({ onSuccess }) {
  const { ingestSyllabus, ingestFromUrl, loading } = useApiClient();

  // ── SECTION 1: Academic Metadata — persists across uploads ───────────────
  const [bos, setBos] = useState('');
  const [department, setDepartment] = useState('');
  const [program, setProgram] = useState('');
  const [semester, setSemester] = useState('');

  // ── SECTION 2: Per-subject content — clears after each upload ────────────
  const [subjectCode, setSubjectCode] = useState('');
  const [subjectName, setSubjectName] = useState('');
  const [cosText, setCosText] = useState('');   // COs belong to THIS subject
  const [pcosText, setPcosText] = useState('');   // PCOs belong to THIS subject
  const [inputMode, setInputMode] = useState('pdf');
  const [pdfFile, setPdfFile] = useState(null);
  const [syllabusUrl, setSyllabusUrl] = useState('');

  // NEW: per-module text input state
  const [textModules, setTextModules] = useState([{ title: '', content: '' }]);

  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // ── Static cascade options ────────────────────────────────────────────────
  const bosOptions = useMemo(() => getBosOptions(), []);
  const deptOptions = useMemo(() => getDeptOptions(bos), [bos]);
  const programOptions = useMemo(() => getProgramOptions(bos, department), [bos, department]);
  const semOptions = useMemo(() => getSemesterOptions(bos, department, program), [bos, department, program]);

  const handleBos = v => { setBos(v); setDepartment(''); setProgram(''); setSemester(''); };
  const handleDept = v => { setDepartment(v); setProgram(''); setSemester(''); };
  const handleProgram = v => { setProgram(v); setSemester(''); };

  // ── Parsers ───────────────────────────────────────────────────────────────
  const parseCOs = raw =>
    raw.split('\n').map(l => l.trim()).filter(Boolean)
      .map(l => { const m = l.match(/^(CO\d+)\s*[:–-]\s*(.+)$/i); return m ? { co_id: m[1].toUpperCase(), text: m[2].trim() } : null; })
      .filter(Boolean);

  const parsePCOs = raw =>
    raw.split('\n').map(l => l.trim()).filter(Boolean)
      .map(l => { const m = l.match(/^(CO\d+)\s*[:–-]\s*(PO\d+)$/i); return m ? { co_id: m[1].toUpperCase(), pco_id: m[2].toUpperCase() } : null; })
      .filter(Boolean);

  const metadataComplete = bos && department && program && semester;

  // Only clears the per-subject content — metadata stays
  const resetSubjectContent = () => {
    setSubjectCode(''); setSubjectName('');
    setCosText(''); setPcosText('');
    setPdfFile(null); setSyllabusUrl('');
    setTextModules([{ title: '', content: '' }]);
  };

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null); setSuccess(null);

    if (!metadataComplete) { setError('Please complete Section 1 (all 4 dropdowns)'); return; }
    if (!subjectCode || !subjectName) { setError('Please enter Subject Code and Subject Name'); return; }
    if (inputMode === 'pdf' && !pdfFile) { setError('Please select a PDF file'); return; }
    if (inputMode === 'text' && !textModules.some(m => m.content.trim())) { setError('Please enter content for at least one module'); return; }
    if (inputMode === 'url' && !syllabusUrl.trim()) { setError('Please enter a URL'); return; }

    const cos = cosText.trim() ? parseCOs(cosText) : [];
    const pcos = pcosText.trim() ? parsePCOs(pcosText) : [];

    try {
      let result;
      if (inputMode === 'url') {
        result = await ingestFromUrl({
          url: syllabusUrl.trim(),
          bos, department, program, semester,
          subject_code: subjectCode,
          subject_name: subjectName,
          cos: cos.length ? JSON.stringify(cos) : undefined,
          pcos: pcos.length ? JSON.stringify(pcos) : undefined,
        });
      } else {
        const fd = new FormData();
        fd.append('mode', inputMode);
        fd.append('bos', bos); fd.append('department', department);
        fd.append('program', program); fd.append('semester', semester);
        fd.append('subject_code', subjectCode); fd.append('subject_name', subjectName);
        if (inputMode === 'pdf') {
          fd.append('file', pdfFile);
        } else {
          // Compile dynamic rows into Format B: "1  Introduction:\nContent..."
          const compiledText = textModules
            .filter(m => m.content.trim())
            .map((m, i) => `${i + 1}  ${m.title.trim() || `Module ${i + 1}`}:\n${m.content.trim()}`)
            .join('\n\n');
          fd.append('text', compiledText);
        }
        if (cos.length) fd.append('cos', JSON.stringify(cos));
        if (pcos.length) fd.append('pcos', JSON.stringify(pcos));
        result = await ingestSyllabus(fd);
      }

      const extras = [];
      if (result.cos_stored) extras.push(`${result.cos_stored} COs`);
      if (result.pcos_stored) extras.push(`${result.pcos_stored} PCOs`);
      const extra = extras.length ? ` (${extras.join(', ')} stored)` : '';
      setSuccess(`✅ "${subjectName}" ingested!${extra}  ID: ${result.syllabus_id}`);
      if (onSuccess) onSuccess(result);
      resetSubjectContent();   // ← metadata intentionally kept
    } catch (err) {
      setError(err.message);
    }
  };

  // ── Helpers ───────────────────────────────────────────────────────────────
  const CascadeSelect = ({ id, label, value, onChange, options, locked, required }) => (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
        {locked && <span className="text-xs text-gray-400 font-normal ml-2">— select above first</span>}
      </label>
      <select
        id={id} value={value} onChange={e => onChange(e.target.value)}
        disabled={locked} required={required && !locked}
        className={`input-field ${locked ? 'opacity-40 cursor-not-allowed bg-gray-100' : ''}`}
      >
        <option value="">— {label} —</option>
        {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
      </select>
    </div>
  );

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="card space-y-5">
      <h3 className="text-xl font-semibold">Ingest Syllabus</h3>

      {error && <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{error}</div>}
      {success && <div className="p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">{success}</div>}

      <form onSubmit={handleSubmit} className="space-y-5">

        {/* ══════════════════════════════════════════════════════════════
            SECTION 1 — Academic Metadata (fill once, persists)
            ══════════════════════════════════════════════════════════ */}
        <div className="border border-indigo-100 rounded-xl p-4 bg-indigo-50/40 space-y-3">
          <div className="flex items-center gap-2">
            <span className="flex-shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full bg-indigo-600 text-white text-xs font-bold">1</span>
            <p className="text-sm font-semibold text-indigo-800">
              Academic Metadata
              <span className="ml-2 font-normal text-indigo-500 text-xs">— fill once, stays between uploads</span>
            </p>
            {metadataComplete && <span className="ml-auto text-xs text-green-600 font-semibold">✓ Ready</span>}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <CascadeSelect id="bos" label="University / BOS" value={bos} onChange={handleBos} options={bosOptions} locked={false} required />
            <CascadeSelect id="department" label="Department" value={department} onChange={handleDept} options={deptOptions} locked={!bos} required />
            <CascadeSelect id="program" label="Program" value={program} onChange={handleProgram} options={programOptions} locked={!department} required />
            <CascadeSelect id="semester" label="Semester" value={semester} onChange={setSemester} options={semOptions} locked={!program} required />
          </div>
        </div>

        {/* ══════════════════════════════════════════════════════════════
            SECTION 2 — Subject Content (resets after each upload)
            ══════════════════════════════════════════════════════════ */}
        <div className={`border rounded-xl p-4 space-y-4 transition-opacity ${metadataComplete ? 'border-gray-200 opacity-100' : 'border-gray-100 opacity-40 pointer-events-none'
          }`}>
          <div className="flex items-center gap-2">
            <span className="flex-shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full bg-gray-700 text-white text-xs font-bold">2</span>
            <p className="text-sm font-semibold text-gray-800">
              Subject Details
              <span className="ml-2 font-normal text-gray-400 text-xs">— specific to this subject / upload</span>
            </p>
          </div>

          {/* Subject Code + Name */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Subject Code <span className="text-red-500">*</span></label>
              <input type="text" value={subjectCode} onChange={e => setSubjectCode(e.target.value)}
                placeholder="e.g., CS501" className="input-field" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Subject Name <span className="text-red-500">*</span></label>
              <input type="text" value={subjectName} onChange={e => setSubjectName(e.target.value)}
                placeholder="e.g., Operating Systems" className="input-field" required />
            </div>
          </div>

          {/* COs — per subject */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Course Outcomes (COs)
              <span className="ml-2 text-xs text-gray-400 font-normal">— for {subjectName || 'this subject'} only</span>
            </label>
            <textarea value={cosText} onChange={e => setCosText(e.target.value)}
              placeholder={"CO1: Understand memory management\nCO2: Apply scheduling algorithms"}
              rows={3} className="input-field font-mono text-sm" />
            <p className="text-xs text-gray-500 mt-1">One per line: <code className="bg-gray-100 px-1 rounded">CO1: description</code></p>
          </div>

          {/* PCOs — per subject */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              CO → PO Mapping
              <span className="ml-2 text-xs text-gray-400 font-normal">— for {subjectName || 'this subject'} only</span>
            </label>
            <textarea value={pcosText} onChange={e => setPcosText(e.target.value)}
              placeholder={"CO1: PO1\nCO2: PO3"} rows={2} className="input-field font-mono text-sm" />
            <p className="text-xs text-gray-500 mt-1">One per line: <code className="bg-gray-100 px-1 rounded">CO1: PO2</code></p>
          </div>

          {/* Input Mode tabs */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Syllabus Source</label>
            <div className="flex flex-wrap gap-2 mb-3">
              {[['pdf', '📄 Upload PDF'], ['text', '📝 Paste Text'], ['url', '🌐 From URL']].map(([m, lbl]) => (
                <button key={m} type="button"
                  onClick={() => {
                    setInputMode(m);
                    setPdfFile(null);
                    setTextModules([{ title: '', content: '' }]);
                    setSyllabusUrl('');
                  }}
                  className={`px-4 py-2 rounded-lg border font-medium text-sm transition-colors ${inputMode === m
                    ? 'bg-gray-800 border-gray-800 text-white'
                    : 'bg-gray-50 border-gray-300 text-gray-700 hover:bg-gray-100'
                    }`}>
                  {lbl}
                </button>
              ))}
            </div>

            {inputMode === 'pdf' && (
              <div>
                <input type="file" accept=".pdf" onChange={e => setPdfFile(e.target.files[0])} className="w-full" required />
                {pdfFile && <p className="mt-1 text-sm text-gray-600">✓ {pdfFile.name}</p>}
              </div>
            )}
            {inputMode === 'text' && (
              <div className="space-y-4">
                {textModules.map((mod, idx) => (
                  <div key={idx} className="border border-gray-200 rounded-lg bg-gray-50 overflow-hidden relative">
                    <div className="bg-gray-100 px-3 py-2 border-b border-gray-200 flex justify-between items-center">
                      <span className="text-xs font-semibold text-gray-700">Module {idx + 1}</span>
                      {textModules.length > 1 && (
                        <button type="button" onClick={() => setTextModules(prev => prev.filter((_, i) => i !== idx))}
                          className="text-gray-400 hover:text-red-500 font-bold p-1 leading-none rounded">
                          &times;
                        </button>
                      )}
                    </div>
                    <div className="p-3 space-y-3">
                      <div>
                        <input type="text" placeholder="Title (e.g. Introduction to Cyber Security)"
                          value={mod.title}
                          onChange={e => {
                            const nt = [...textModules];
                            nt[idx].title = e.target.value;
                            setTextModules(nt);
                          }}
                          className="w-full text-sm font-semibold bg-transparent border-b border-gray-300 focus:border-gray-800 outline-none pb-1 transition-colors"
                        />
                      </div>
                      <div>
                        <textarea placeholder="Paste topics and contents here..." rows={4}
                          value={mod.content}
                          onChange={e => {
                            const nt = [...textModules];
                            nt[idx].content = e.target.value;
                            setTextModules(nt);
                          }}
                          className="w-full text-sm resize-y outline-none bg-transparent"
                          required={idx === 0}
                        />
                      </div>
                    </div>
                  </div>
                ))}

                <button type="button"
                  onClick={() => setTextModules(prev => [...prev, { title: '', content: '' }])}
                  className="w-full py-2 border-2 border-dashed border-gray-300 text-gray-500 hover:border-gray-400 hover:text-gray-700 rounded-lg text-sm font-medium transition-colors">
                  + Add Another Module
                </button>
              </div>
            )}
            {inputMode === 'url' && (
              <div>
                <input type="url" value={syllabusUrl} onChange={e => setSyllabusUrl(e.target.value)}
                  placeholder="https://makaut.ac.in/syllabus.pdf" className="input-field" required />
                <p className="text-xs text-gray-500 mt-1">Supports direct PDF links or HTML pages.</p>
              </div>
            )}
          </div>
        </div>

        <button type="submit" disabled={loading || !metadataComplete} className="btn-primary w-full">
          {loading
            ? (inputMode === 'url' ? 'Downloading & Ingesting...' : 'Ingesting...')
            : `Ingest ${subjectName || 'Subject'}`}
        </button>

        {!metadataComplete && (
          <p className="text-xs text-center text-gray-400">Complete Section 1 first to unlock ingestion</p>
        )}
      </form>
    </div>
  );
}

export default SyllabusUploadForm;
