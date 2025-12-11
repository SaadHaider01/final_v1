import React from 'react';

function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-gray-900 text-gray-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <h3 className="text-white font-semibold text-lg mb-4">
              RAG-Based Syllabus Analyzer
            </h3>
            <p className="text-sm">
              An intelligent system for automated syllabus relevance checking using
              Retrieval-Augmented Generation, SBERT embeddings, and LLM validation.
            </p>
          </div>

          <div>
            <h3 className="text-white font-semibold text-lg mb-4">Quick Links</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="/problem" className="hover:text-primary-400 transition-colors">
                  Problem Statement
                </a>
              </li>
              <li>
                <a href="/architecture" className="hover:text-primary-400 transition-colors">
                  System Architecture
                </a>
              </li>
              <li>
                <a href="/playground" className="hover:text-primary-400 transition-colors">
                  Try Demo
                </a>
              </li>
              <li>
                <a href="/results" className="hover:text-primary-400 transition-colors">
                  Experimental Results
                </a>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="text-white font-semibold text-lg mb-4">Technology Stack</h3>
            <ul className="space-y-2 text-sm">
              <li>• Sentence-BERT Embeddings</li>
              <li>• ChromaDB Vector Store</li>
              <li>• Cosine Similarity Gatekeeper</li>
              <li>• LLM-based Curriculum Validator</li>
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t border-gray-800 text-center text-sm">
          <p>
            © {currentYear} RAG-Based Syllabus Analyzer. Final Year Project - Department of Information Technology.
          </p>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
