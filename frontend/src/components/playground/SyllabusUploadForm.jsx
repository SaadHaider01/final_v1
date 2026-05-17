import React, { useState } from 'react';
import { useApiClient } from '../../hooks/useApiClient';

/**
 * SyllabusUploadForm — Curriculum-Driven Version
 *
 * Two-phase ingestion flow:
 *  Phase 1: Upload PDF/URL → backend parses hierarchy → frontend shows subject cards
 *  Phase 2: User selects subjects → "Ingest Selected" or "Ingest All" → embeddings generated
 *
 * Text mode: fallback to classic single-syllabus ingestion (unchanged contract).
 *
 * Static makautData dependency has been REMOVED.
 * All metadata now comes from the curriculum itself.
 */
function SyllabusUploadForm({ onSuccess }) {
  const { ingestSyllabus, ingestFromUrl, parseCurriculum, ingestSelected, loading } = useApiClient();

  // ── Input mode ─────────────────────────────────────────────────────────────
  const [inputMode, setInputMode] = useState('pdf');
  const [pdfFile, setPdfFile]     = useState(null);
  const [syllabusUrl, setSyllabusUrl] = useState('');

  // Text-mode (legacy single-subject fallback)
  const [textModules, setTextModules] = useState([{ title: '', content: '' }]);
  const [subjectCode, setSubjectCode] = useState('');
  const [subjectName, setSubjectName] = useState('');
  const [cosText, setCosText]   = useState('');
  const [pcosText, setPcosText] = useState('');

  // ── Phase 1 state: parsed curriculum preview ───────────────────────────────
  const [phase, setPhase]               = useState('upload');   // 'upload' | 'preview'
  const [parseId, setParseId]           = useState(null);
  const [parsedSegments, setParsedSegments] = useState([]);
  const [selectedIds, setSelectedIds]   = useState(new Set());

  const [error, setError]     = useState(null);
  const [success, setSuccess] = useState(null);

  // ── Parsers (CO/PCO — text mode only) ─────────────────────────────────────
  const parseCOs = raw =>
    raw.split('\n').map(l => l.trim()).filter(Boolean)
      .map(l => { const m = l.match(/^(CO\d+)\s*[:–-]\s*(.+)$/i); return m ? { co_id: m[1].toUpperCase(), text: m[2].trim() } : null; })
      .filter(Boolean);

  const parsePCOs = raw =>
    raw.split('\n').map(l => l.trim()).filter(Boolean)
      .map(l => { const m = l.match(/^(CO\d+)\s*[:–-]\s*(PO\d+)$/i); return m ? { co_id: m[1].toUpperCase(), pco_id: m[2].toUpperCase() } : null; })
      .filter(Boolean);

  // ── Phase 1: Parse curriculum (PDF or URL) ─────────────────────────────────
  const handleParseCurriculum = async () => {
    setError(null); setSuccess(null);

    try {
      let result;
      if (inputMode === 'pdf') {
        if (!pdfFile) { setError('Please select a PDF file'); return; }
        const fd = new FormData();
        fd.append('mode', 'pdf');
        fd.append('file', pdfFile);
        result = await parseCurriculum(fd);
      } else {
        if (!syllabusUrl.trim()) { setError('Please enter a URL'); return; }
        result = await parseCurriculum({ mode: 'url', url: syllabusUrl.trim() });
      }

      if (!result.segments || result.segments.length === 0) {
        setError(result.message || 'No subjects detected in curriculum. Try pasting text directly.');
        return;
      }

      setParseId(result.parse_id);
      setParsedSegments(result.segments);
      // Pre-select subjects that are NOT already ingested
      const preSelected = new Set(
        result.segments.filter(s => !s.already_ingested).map(s => s.syllabus_id)
      );
      setSelectedIds(preSelected);
      setPhase('preview');
    } catch (err) {
      setError(err.message);
    }
  };

  // ── Phase 2: Ingest selected subjects ─────────────────────────────────────
  const handleIngestSelected = async (all = false) => {
    setError(null); setSuccess(null);

    if (!all && selectedIds.size === 0) {
      setError('Please select at least one subject to ingest');
      return;
    }

    try {
      const payload = {
        parse_id: parseId,
        syllabus_ids: all ? [] : [...selectedIds],
        ingest_all: all,
      };
      const result = await ingestSelected(payload);

      const deptsCount = new Set(parsedSegments.map(s => s.department).filter(Boolean)).size;
      const semsCount  = new Set(parsedSegments.map(s => s.semester).filter(Boolean)).size;

      setSuccess({
        type: 'stats',
        parsed: all ? parsedSegments.length : selectedIds.size,
        ingested: result.ingested?.length || 0,
        skipped: result.skipped_duplicates?.length || 0,
        chunks: result.chunks_generated || 0,
        depts: deptsCount,
        sems: semsCount
      });
      setPhase('upload');
      setParsedSegments([]);
      setParseId(null);
      setPdfFile(null);
      setSyllabusUrl('');
      if (onSuccess) onSuccess(result);
    } catch (err) {
      setError(err.message);
    }
  };

  // ── Text mode (legacy single-subject, unchanged API) ─────────────────────
  const handleTextIngest = async (e) => {
    e.preventDefault();
    setError(null); setSuccess(null);

    if (!textModules.some(m => m.content.trim())) {
      setError('Please enter content for at least one module');
      return;
    }

    const cos  = cosText.trim()  ? parseCOs(cosText)   : [];
    const pcos = pcosText.trim() ? parsePCOs(pcosText) : [];

    const compiledText = textModules
      .filter(m => m.content.trim())
      .map((m, i) => `${i + 1}  ${m.title.trim() || `Module ${i + 1}`}:\n${m.content.trim()}`)
      .join('\n\n');

    const fd = new FormData();
    fd.append('mode', 'text');
    fd.append('text', compiledText);
    if (subjectCode) fd.append('subject_code', subjectCode);
    if (subjectName) fd.append('subject_name', subjectName);
    if (cos.length)  fd.append('cos', JSON.stringify(cos));
    if (pcos.length) fd.append('pcos', JSON.stringify(pcos));

    try {
      const result = await ingestSyllabus(fd);
      setSuccess(`✅ Ingested! ID: ${result.syllabus_ids?.[0] || result.syllabus_id || '—'}`);
      setTextModules([{ title: '', content: '' }]);
      setSubjectCode(''); setSubjectName('');
      setCosText(''); setPcosText('');
      if (onSuccess) onSuccess(result);
    } catch (err) {
      setError(err.message);
    }
  };

  // ── Toggle subject selection ───────────────────────────────────────────────
  const toggleSubject = (sid) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(sid) ? next.delete(sid) : next.add(sid);
      return next;
    });
  };

  const selectAll   = () => setSelectedIds(new Set(parsedSegments.filter(s => !s.already_ingested).map(s => s.syllabus_id)));
  const selectNone  = () => setSelectedIds(new Set());

  // ═══════════════════════════════════════════════════════════════════
  // RENDER — Phase 1: Upload
  // ═══════════════════════════════════════════════════════════════════
  if (phase === 'upload') {
    return (
      <div className="card space-y-5">
        <h3 className="text-xl font-semibold">Ingest Curriculum</h3>

        {error   && <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{error}</div>}
        {success && success.type === 'stats' && (
          <div className="p-4 bg-green-50 border border-green-200 rounded-xl">
            <h4 className="text-sm font-bold text-green-900 mb-2">✅ Curriculum Ingested Successfully</h4>
            <div className="grid grid-cols-3 md:grid-cols-5 gap-2 text-center">
              <div className="bg-white p-2 rounded border border-green-100">
                <div className="text-lg font-bold text-green-700">{success.depts}</div>
                <div className="text-[9px] uppercase font-semibold text-green-600">Depts</div>
              </div>
              <div className="bg-white p-2 rounded border border-green-100">
                <div className="text-lg font-bold text-green-700">{success.sems}</div>
                <div className="text-[9px] uppercase font-semibold text-green-600">Sems</div>
              </div>
              <div className="bg-white p-2 rounded border border-green-100">
                <div className="text-lg font-bold text-green-700">{success.parsed}</div>
                <div className="text-[9px] uppercase font-semibold text-green-600">Subjects</div>
              </div>
              <div className="bg-white p-2 rounded border border-green-100">
                <div className="text-lg font-bold text-green-700">{success.ingested}</div>
                <div className="text-[9px] uppercase font-semibold text-green-600">Embedded</div>
              </div>
              <div className="bg-white p-2 rounded border border-green-100 col-span-3 md:col-span-1">
                <div className="text-lg font-bold text-green-700">{success.chunks}</div>
                <div className="text-[9px] uppercase font-semibold text-green-600">Chunks</div>
              </div>
            </div>
            {success.skipped > 0 && (
              <p className="text-[10px] text-green-600 mt-2 text-center italic">
                ℹ️ {success.skipped} subject(s) were already in the database and were skipped.
              </p>
            )}
          </div>
        )}
        {success && typeof success === 'string' && (
          <div className="p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">{success}</div>
        )}

        {/* Mode tabs */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Source</label>
          <div className="flex flex-wrap gap-2">
            {[['pdf', '📄 Upload PDF'], ['url', '🌐 From URL'], ['text', '📝 Paste Text']].map(([m, lbl]) => (
              <button key={m} type="button"
                onClick={() => { setInputMode(m); setPdfFile(null); setSyllabusUrl(''); }}
                className={`px-4 py-2 rounded-lg border font-medium text-sm transition-colors ${inputMode === m
                  ? 'bg-gray-800 border-gray-800 text-white'
                  : 'bg-gray-50 border-gray-300 text-gray-700 hover:bg-gray-100'}`}>
                {lbl}
              </button>
            ))}
          </div>
        </div>

        {/* ── PDF mode ── */}
        {inputMode === 'pdf' && (
          <div className="space-y-4">
            <div className="border-2 border-dashed border-indigo-200 rounded-xl p-6 bg-indigo-50/30 text-center">
              <p className="text-sm text-indigo-700 font-medium mb-3">
                📋 Upload a full curriculum PDF — the system will automatically detect all subjects
              </p>
              <input type="file" accept=".pdf,.docx,.pptx"
                onChange={e => setPdfFile(e.target.files[0])}
                className="w-full" />
              {pdfFile && <p className="mt-2 text-sm text-indigo-600 font-medium">✓ {pdfFile.name}</p>}
            </div>
            <button type="button" onClick={handleParseCurriculum} disabled={loading || !pdfFile}
              className="btn-primary w-full">
              {loading ? '⏳ Detecting Subjects...' : '🔍 Parse & Preview Subjects'}
            </button>
          </div>
        )}

        {/* ── URL mode ── */}
        {inputMode === 'url' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Curriculum URL</label>
              <input type="url" value={syllabusUrl} onChange={e => setSyllabusUrl(e.target.value)}
                placeholder="https://university.edu/curriculum.pdf"
                className="input-field" />
              <p className="text-xs text-gray-500 mt-1">Supports direct PDF links or HTML pages.</p>
            </div>
            <button type="button" onClick={handleParseCurriculum} disabled={loading || !syllabusUrl.trim()}
              className="btn-primary w-full">
              {loading ? '⏳ Downloading & Parsing...' : '🔍 Parse & Preview Subjects'}
            </button>
          </div>
        )}

        {/* ── Text mode (single subject, legacy flow) ── */}
        {inputMode === 'text' && (
          <form onSubmit={handleTextIngest} className="space-y-4">
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
              ℹ️ Text mode ingests a single subject directly. For multi-subject curriculum PDFs, use PDF or URL mode.
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subject Code <span className="text-gray-400 text-xs">(optional)</span></label>
                <input type="text" value={subjectCode} onChange={e => setSubjectCode(e.target.value)}
                  placeholder="e.g. IT801B" className="input-field" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subject Name <span className="text-gray-400 text-xs">(optional)</span></label>
                <input type="text" value={subjectName} onChange={e => setSubjectName(e.target.value)}
                  placeholder="Auto-detected if blank" className="input-field" />
              </div>
            </div>

            {/* Modules */}
            <div className="space-y-3">
              {textModules.map((mod, idx) => (
                <div key={idx} className="border border-gray-200 rounded-lg bg-gray-50 overflow-hidden">
                  <div className="bg-gray-100 px-3 py-2 border-b border-gray-200 flex justify-between items-center">
                    <span className="text-xs font-semibold text-gray-700">Module {idx + 1}</span>
                    {textModules.length > 1 && (
                      <button type="button" onClick={() => setTextModules(p => p.filter((_, i) => i !== idx))}
                        className="text-gray-400 hover:text-red-500 font-bold p-1">×</button>
                    )}
                  </div>
                  <div className="p-3 space-y-2">
                    <input type="text" placeholder="Title (e.g. Cryptography Basics)"
                      value={mod.title} onChange={e => { const n=[...textModules]; n[idx].title=e.target.value; setTextModules(n); }}
                      className="w-full text-sm font-semibold bg-transparent border-b border-gray-300 focus:border-gray-800 outline-none pb-1" />
                    <textarea placeholder="Paste topics and contents here..." rows={4}
                      value={mod.content} onChange={e => { const n=[...textModules]; n[idx].content=e.target.value; setTextModules(n); }}
                      className="w-full text-sm resize-y outline-none bg-transparent" required={idx===0} />
                  </div>
                </div>
              ))}
              <button type="button" onClick={() => setTextModules(p => [...p, { title: '', content: '' }])}
                className="w-full py-2 border-2 border-dashed border-gray-300 text-gray-500 hover:border-gray-400 rounded-lg text-sm font-medium transition-colors">
                + Add Another Module
              </button>
            </div>

            {/* COs */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Course Outcomes <span className="text-xs text-gray-400">(optional)</span></label>
              <textarea value={cosText} onChange={e => setCosText(e.target.value)}
                placeholder={"CO1: Understand memory management\nCO2: Apply scheduling algorithms"}
                rows={2} className="input-field font-mono text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">CO → PO Mapping <span className="text-xs text-gray-400">(optional)</span></label>
              <textarea value={pcosText} onChange={e => setPcosText(e.target.value)}
                placeholder={"CO1: PO1\nCO2: PO3"} rows={2} className="input-field font-mono text-sm" />
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? 'Ingesting...' : 'Ingest Subject'}
            </button>
          </form>
        )}
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // RENDER — Phase 2: Subject Preview & Selection
  // ═══════════════════════════════════════════════════════════════════
  return (
    <div className="card space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-semibold">Select Subjects to Ingest</h3>
          <p className="text-sm text-gray-500 mt-1">
            {parsedSegments.length} subject{parsedSegments.length !== 1 ? 's' : ''} detected in curriculum
          </p>
        </div>
        <button type="button" onClick={() => { setPhase('upload'); setParsedSegments([]); setParseId(null); }}
          className="text-sm text-gray-500 hover:text-gray-800 border border-gray-300 px-3 py-1.5 rounded-lg transition-colors">
          ← Back
        </button>
      </div>

      {error   && <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{error}</div>}
      {success && <div className="p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">{success}</div>}

      {/* Selection controls */}
      <div className="flex gap-2 items-center text-xs">
        <button type="button" onClick={selectAll}  className="text-indigo-600 hover:underline">Select All New</button>
        <span className="text-gray-300">|</span>
        <button type="button" onClick={selectNone} className="text-gray-500 hover:underline">Deselect All</button>
        <span className="ml-auto text-gray-500">{selectedIds.size} selected</span>
      </div>

      {/* Subject cards */}
      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
        {parsedSegments.map(seg => {
          const isSelected = selectedIds.has(seg.syllabus_id);
          const isIngested = seg.already_ingested;
          return (
            <div
              key={seg.syllabus_id}
              onClick={() => !isIngested && toggleSubject(seg.syllabus_id)}
              className={`border rounded-xl p-3 transition-all cursor-pointer ${
                isIngested
                  ? 'border-gray-200 bg-gray-50 opacity-60 cursor-not-allowed'
                  : isSelected
                    ? 'border-indigo-400 bg-indigo-50 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-gray-300'
              }`}>
              <div className="flex items-start gap-3">
                {/* Checkbox */}
                <div className={`flex-shrink-0 w-5 h-5 mt-0.5 rounded border-2 flex items-center justify-center ${
                  isIngested ? 'border-green-400 bg-green-100' :
                  isSelected  ? 'border-indigo-500 bg-indigo-500' :
                  'border-gray-300 bg-white'}`}>
                  {isIngested && <span className="text-green-600 text-xs">✓</span>}
                  {!isIngested && isSelected && <span className="text-white text-xs">✓</span>}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm text-gray-900 truncate">{seg.subject_name}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium border ${
                      seg.elective_type === 'CORE' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                      seg.elective_type === 'PEC'  ? 'bg-purple-50 text-purple-700 border-purple-200' :
                      seg.elective_type === 'OEC'  ? 'bg-orange-50 text-orange-700 border-orange-200' :
                      seg.elective_type === 'LAB'  ? 'bg-green-50 text-green-700 border-green-200' :
                      'bg-gray-50 text-gray-600 border-gray-200'
                    }`}>{seg.elective_type}</span>
                    {isIngested && <span className="text-xs text-green-600 font-medium">Already stored</span>}
                  </div>

                  <div className="text-xs text-gray-500 mt-0.5">
                    {seg.department && <span>{seg.department}</span>}
                    {seg.semester && <span> · Sem {seg.semester}</span>}
                    {seg.subject_code && <span> · {seg.subject_code}</span>}
                  </div>

                  {seg.modules && seg.modules.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {seg.modules.slice(0, 4).map((m, i) => (
                        <span key={i} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                          {m.replace(/^(Module|Unit|Chapter)\s*/i, 'U').slice(0, 30)}
                        </span>
                      ))}
                      {seg.modules.length > 4 && (
                        <span className="text-xs text-gray-400">+{seg.modules.length - 4} more</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Action buttons */}
      <div className="flex gap-3">
        <button type="button"
          onClick={() => handleIngestSelected(false)}
          disabled={loading || selectedIds.size === 0}
          className="btn-primary flex-1">
          {loading ? '⏳ Ingesting...' : `Ingest Selected (${selectedIds.size})`}
        </button>
        <button type="button"
          onClick={() => handleIngestSelected(true)}
          disabled={loading}
          className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg font-medium text-sm hover:bg-gray-50 transition-colors">
          Ingest All
        </button>
      </div>
    </div>
  );
}

export default SyllabusUploadForm;
