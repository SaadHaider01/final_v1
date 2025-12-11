import React from 'react';
import { Link } from 'react-router-dom';

function Home() {
  return (
    <div>
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-primary-600 via-primary-700 to-accent-700 text-white">
        <div className="section-container text-center">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            RAG-Based Semantic Question Analyzer
          </h1>
          <p className="text-xl md:text-2xl mb-8 max-w-4xl mx-auto text-primary-100">
            Intelligent automated syllabus relevance verification using Retrieval-Augmented Generation, 
            SBERT embeddings, and LLM-based curriculum validation
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              to="/playground"
              className="bg-white text-primary-700 hover:bg-gray-100 font-semibold py-3 px-8 rounded-lg transition-colors duration-200"
            >
              Try Live Demo
            </Link>
            <Link
              to="/architecture"
              className="bg-primary-500 hover:bg-primary-400 text-white font-semibold py-3 px-8 rounded-lg border-2 border-white transition-colors duration-200"
            >
              View Architecture
            </Link>
          </div>
        </div>
      </section>

      {/* Abstract Section */}
      <section className="section-container bg-white">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-center mb-8">Project Abstract</h2>
          <p className="text-lg text-gray-700 leading-relaxed mb-6">
            This project addresses the critical challenge of ensuring exam questions align with prescribed 
            academic syllabi. Manual verification is time-consuming, inconsistent, and prone to human error, 
            leading to potential unfairness in assessments.
          </p>
          <p className="text-lg text-gray-700 leading-relaxed mb-6">
            Our solution implements a <strong>Retrieval-Augmented Generation (RAG)</strong> pipeline that 
            combines semantic embeddings, vector similarity search, and LLM-based validation to automatically 
            determine whether exam questions fall within the prescribed syllabus boundaries.
          </p>
          <p className="text-lg text-gray-700 leading-relaxed">
            The system features a two-stage architecture: a <strong>Cosine Gatekeeper</strong> that filters 
            semantically distant questions to reduce computational costs, followed by an <strong>LLM Curriculum 
            Validator</strong> that makes the final judgment using few-shot prompting with domain-agnostic rules.
          </p>
        </div>
      </section>

      {/* Key Features */}
      <section className="section-container bg-gray-50">
        <h2 className="text-center mb-12">Key Features & Impact</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="card text-center">
            <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold mb-3">Automated Verification</h3>
            <p className="text-gray-600">
              Eliminates manual syllabus checking, reducing workload for educators and examination boards
            </p>
          </div>

          <div className="card text-center">
            <div className="w-16 h-16 bg-accent-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-accent-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold mb-3">High Accuracy</h3>
            <p className="text-gray-600">
              Combines vector similarity with LLM intelligence to handle keyword traps and semantic nuances
            </p>
          </div>

          <div className="card text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold mb-3">Cost Efficient</h3>
            <p className="text-gray-600">
              Gatekeeper reduces unnecessary LLM calls by up to 70%, significantly lowering operational costs
            </p>
          </div>

          <div className="card text-center">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold mb-3">Scalable Architecture</h3>
            <p className="text-gray-600">
              Designed for multi-department, multi-subject deployment across entire universities
            </p>
          </div>

          <div className="card text-center">
            <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold mb-3">Fairer Assessments</h3>
            <p className="text-gray-600">
              Ensures consistency and reduces bias in determining question relevance across all evaluations
            </p>
          </div>

          <div className="card text-center">
            <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold mb-3">Domain Agnostic</h3>
            <p className="text-gray-600">
              Works across any engineering discipline and adaptable to non-engineering subjects
            </p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="section-container bg-gradient-to-r from-primary-600 to-accent-600 text-white text-center">
        <h2 className="text-white mb-6">Ready to explore the system?</h2>
        <p className="text-xl text-primary-100 mb-8 max-w-2xl mx-auto">
          Try our interactive demo to see how the RAG-based analyzer processes questions and validates 
          their relevance against syllabus content.
        </p>
        <Link
          to="/playground"
          className="inline-block bg-white text-primary-700 hover:bg-gray-100 font-semibold py-3 px-8 rounded-lg transition-colors duration-200"
        >
          Launch Demo Playground
        </Link>
      </section>
    </div>
  );
}

export default Home;
