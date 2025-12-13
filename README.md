
```
final_year_project_v1
├─ backend
│  ├─ app.py
│  ├─ config.py
│  ├─ data
│  │  ├─ embeddings
│  │  ├─ syllabi
│  │  └─ vector_db
│  │     ├─ chroma.sqlite3
│  │     └─ d2e61397-0133-4351-a3cf-684a1fb1299d
│  │        ├─ data_level0.bin
│  │        ├─ header.bin
│  │        ├─ length.bin
│  │        └─ link_lists.bin
│  ├─ models
│  │  └─ embedder.py
│  ├─ processors
│  │  ├─ pdf_reader.py
│  │  └─ text_chunker.py
│  ├─ validators
│  │  └─ llm_gate.py
│  └─ vectorstores
│     └─ chroma_store.py
├─ frontend
│  ├─ index.html
│  ├─ package-lock.json
│  ├─ package.json
│  ├─ postcss.config.cjs
│  ├─ src
│  │  ├─ App.jsx
│  │  ├─ components
│  │  │  ├─ common
│  │  │  │  ├─ Card.jsx
│  │  │  │  └─ SectionHeader.jsx
│  │  │  ├─ layout
│  │  │  │  ├─ Footer.jsx
│  │  │  │  └─ Navbar.jsx
│  │  │  └─ playground
│  │  │     ├─ AnalysisResultPanel.jsx
│  │  │     ├─ QuestionForm.jsx
│  │  │     └─ SyllabusUploadForm.jsx
│  │  ├─ config
│  │  │  └─ apiConfig.js
│  │  ├─ hooks
│  │  │  └─ useApiClient.js
│  │  ├─ index.css
│  │  ├─ main.jsx
│  │  ├─ pages
│  │  │  ├─ About.jsx
│  │  │  ├─ Architecture.jsx
│  │  │  ├─ Home.jsx
│  │  │  ├─ Playground.jsx
│  │  │  ├─ Problem.jsx
│  │  │  ├─ References.jsx
│  │  │  └─ Results.jsx
│  │  ├─ router.jsx
│  │  └─ utils
│  │     └─ formatters.js
│  ├─ tailwind.config.cjs
│  └─ vite.config.js
└─ README.md

```