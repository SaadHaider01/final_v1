import React from 'react';
import SectionHeader from '../components/common/SectionHeader';
import Card from '../components/common/Card';

function Problem() {
  return (
    <div className="section-container">
      <SectionHeader
        title="Problem Statement"
        subtitle="Understanding the challenge of manual syllabus relevance verification in academic assessments"
      />

      <div className="max-w-4xl mx-auto space-y-8">
        <Card>
          <h3 className="text-2xl font-semibold mb-4">The Challenge</h3>
          <p className="text-gray-700 leading-relaxed mb-4">
            In academic institutions, ensuring that examination questions align with the prescribed syllabus 
            is critical for fair and valid assessment. However, manual verification of question-syllabus 
            alignment presents several significant challenges:
          </p>
          <ul className="list-disc list-inside space-y-2 text-gray-700 ml-4">
            <li><strong>Time-Consuming Process:</strong> Educators and examination boards must manually review each question against syllabus documents</li>
            <li><strong>Inconsistency:</strong> Different reviewers may interpret syllabus boundaries differently, leading to inconsistent decisions</li>
            <li><strong>Human Error:</strong> Fatigue and cognitive biases can result in incorrect classifications</li>
            <li><strong>Scalability Issues:</strong> As universities grow and offer more courses, manual verification becomes increasingly impractical</li>
            <li><strong>Keyword Traps:</strong> Questions may share terminology with the syllabus but address topics outside its scope</li>
          </ul>
        </Card>

        <Card>
          <h3 className="text-2xl font-semibold mb-4">Real-World Impact</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <h4 className="font-semibold text-red-900 mb-2">For Students</h4>
              <p className="text-red-800 text-sm">
                Out-of-syllabus questions create unfair assessments, potentially affecting grades, 
                academic progression, and future opportunities.
              </p>
            </div>
            <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
              <h4 className="font-semibold text-orange-900 mb-2">For Educators</h4>
              <p className="text-orange-800 text-sm">
                Manual verification adds significant workload, diverting time from teaching and 
                research activities.
              </p>
            </div>
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <h4 className="font-semibold text-yellow-900 mb-2">For Institutions</h4>
              <p className="text-yellow-800 text-sm">
                Inconsistent verification can damage institutional reputation and lead to disputes 
                over assessment fairness.
              </p>
            </div>
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <h4 className="font-semibold text-blue-900 mb-2">For Quality Assurance</h4>
              <p className="text-blue-800 text-sm">
                Lack of systematic verification makes it difficult to maintain and audit assessment 
                quality standards.
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <h3 className="text-2xl font-semibold mb-4">The Need for Automation</h3>
          <p className="text-gray-700 leading-relaxed mb-4">
            Given these challenges, there is a pressing need for an automated, intelligent system that can:
          </p>
          <div className="space-y-3">
            <div className="flex items-start space-x-3">
              <svg className="w-6 h-6 text-green-600 mt-1 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <p className="text-gray-700">
                <strong>Process questions rapidly</strong> without human intervention
              </p>
            </div>
            <div className="flex items-start space-x-3">
              <svg className="w-6 h-6 text-green-600 mt-1 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <p className="text-gray-700">
                <strong>Provide consistent decisions</strong> based on objective criteria
              </p>
            </div>
            <div className="flex items-start space-x-3">
              <svg className="w-6 h-6 text-green-600 mt-1 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <p className="text-gray-700">
                <strong>Understand semantic relationships</strong> beyond simple keyword matching
              </p>
            </div>
            <div className="flex items-start space-x-3">
              <svg className="w-6 h-6 text-green-600 mt-1 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <p className="text-gray-700">
                <strong>Detect keyword traps</strong> and semantically related but out-of-scope questions
              </p>
            </div>
            <div className="flex items-start space-x-3">
              <svg className="w-6 h-6 text-green-600 mt-1 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <p className="text-gray-700">
                <strong>Scale across multiple departments</strong> and disciplines
              </p>
            </div>
          </div>
        </Card>

        <Card className="bg-primary-50 border-primary-200">
          <h3 className="text-2xl font-semibold mb-4">Our Solution</h3>
          <p className="text-gray-700 leading-relaxed">
            This project addresses these challenges through a <strong>RAG-based semantic question analyzer</strong> that 
            combines the power of modern NLP techniques: dense embeddings from Sentence-BERT, efficient vector similarity 
            search, a cosine similarity gatekeeper for cost optimization, and LLM-based curriculum validation for 
            nuanced decision-making. The result is an automated, scalable, and highly accurate system for syllabus 
            relevance verification.
          </p>
        </Card>
      </div>
    </div>
  );
}

export default Problem;
