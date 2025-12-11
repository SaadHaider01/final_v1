import React from 'react';
import SectionHeader from '../components/common/SectionHeader';
import Card from '../components/common/Card';

function References() {
  const references = [
    {
      category: 'Embeddings & Semantic Search',
      papers: [
        {
          title: 'Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks',
          authors: 'Nils Reimers, Iryna Gurevych',
          venue: 'EMNLP 2019',
          description: 'Foundation of our semantic embedding approach for syllabus chunks and questions',
        },
        {
          title: 'Efficient Natural Language Response Suggestion for Smart Reply',
          authors: 'Matthew Henderson et al.',
          venue: 'arXiv 2017',
          description: 'Inspired our use of semantic similarity for response classification tasks',
        },
      ],
    },
    {
      category: 'Retrieval-Augmented Generation',
      papers: [
        {
          title: 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks',
          authors: 'Patrick Lewis et al.',
          venue: 'NeurIPS 2020',
          description: 'Core RAG architecture combining retrieval with generative models',
        },
        {
          title: 'REALM: Retrieval-Augmented Language Model Pre-Training',
          authors: 'Kelvin Guu et al.',
          venue: 'ICML 2020',
          description: 'Demonstrated effectiveness of retrieval-based augmentation for language understanding',
        },
      ],
    },
    {
      category: 'Vector Databases & Similarity Search',
      papers: [
        {
          title: 'Billion-scale similarity search with GPUs',
          authors: 'Jeff Johnson, Matthijs Douze, Hervé Jégou',
          venue: 'IEEE Transactions on Big Data 2019',
          description: 'FAISS algorithm for efficient approximate nearest neighbor search',
        },
        {
          title: 'ChromaDB: Open-source embedding database',
          authors: 'Chroma Team',
          venue: 'GitHub 2023',
          description: 'Our chosen vector store for embedding storage and retrieval',
        },
      ],
    },
    {
      category: 'Few-Shot Learning & Prompting',
      papers: [
        {
          title: 'Language Models are Few-Shot Learners',
          authors: 'Tom B. Brown et al.',
          venue: 'NeurIPS 2020',
          description: 'Foundation for our few-shot prompting strategy with the LLM validator',
        },
        {
          title: 'Chain-of-Thought Prompting Elicits Reasoning in Large Language Models',
          authors: 'Jason Wei et al.',
          venue: 'NeurIPS 2022',
          description: 'Informed our approach to structured LLM reasoning',
        },
      ],
    },
    {
      category: 'Educational Technology & Assessment',
      papers: [
        {
          title: 'Automated Question Generation and Answer Assessment: A Survey',
          authors: 'Anubhav Jangra et al.',
          venue: 'Research in Learning Technology 2021',
          description: 'Survey of automated assessment techniques in education',
        },
        {
          title: 'Intelligent Tutoring Systems: Past, Present, and Future',
          authors: 'Beverly Park Woolf',
          venue: 'Handbook of Research on Educational Communications 2008',
          description: 'Context for AI-driven educational assessment systems',
        },
      ],
    },
  ];

  const tools = [
    {
      name: 'Sentence-Transformers',
      description: 'Python library providing pre-trained SBERT models',
      url: 'https://www.sbert.net/',
    },
    {
      name: 'ChromaDB',
      description: 'Open-source embedding database for vector storage',
      url: 'https://www.trychroma.com/',
    },
    {
      name: 'Hugging Face Transformers',
      description: 'Library for loading and running local LLMs',
      url: 'https://huggingface.co/transformers/',
    },
    {
      name: 'PyPDF2',
      description: 'PDF text extraction library',
      url: 'https://pypdf2.readthedocs.io/',
    },
    {
      name: 'Flask',
      description: 'Python web framework for REST API',
      url: 'https://flask.palletsprojects.com/',
    },
    {
      name: 'React',
      description: 'Frontend JavaScript library',
      url: 'https://react.dev/',
    },
    {
      name: 'Tailwind CSS',
      description: 'Utility-first CSS framework',
      url: 'https://tailwindcss.com/',
    },
  ];

  return (
    <div className="section-container">
      <SectionHeader
        title="References & Resources"
        subtitle="Academic foundations and technical resources"
      />

      <div className="max-w-5xl mx-auto space-y-8">
        {/* Academic References */}
        {references.map((section, idx) => (
          <Card key={idx}>
            <h3 className="text-xl font-semibold text-primary-700 mb-4">{section.category}</h3>
            <div className="space-y-4">
              {section.papers.map((paper, paperIdx) => (
                <div key={paperIdx} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                  <div className="font-semibold text-gray-900 mb-1">{paper.title}</div>
                  <div className="text-sm text-gray-600 mb-2">
                    {paper.authors} • <span className="italic">{paper.venue}</span>
                  </div>
                  <div className="text-sm text-gray-700">{paper.description}</div>
                </div>
              ))}
            </div>
          </Card>
        ))}

        {/* Tools & Technologies */}
        <Card className="bg-gradient-to-br from-primary-50 to-accent-50 border-primary-200">
          <h3 className="text-xl font-semibold mb-4">Tools & Technologies</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {tools.map((tool, idx) => (
              <div key={idx} className="p-4 bg-white rounded-lg border border-gray-200">
                <div className="font-semibold text-gray-900 mb-1">{tool.name}</div>
                <div className="text-sm text-gray-700 mb-2">{tool.description}</div>
                <a
                  href={tool.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                >
                  Learn more →
                </a>
              </div>
            ))}
          </div>
        </Card>

        {/* Additional Resources */}
        <Card>
          <h3 className="text-xl font-semibold mb-4">Additional Resources</h3>
          <div className="space-y-3 text-gray-700">
            <div>
              <strong>Cosine Similarity:</strong> Standard metric for measuring semantic similarity in 
              high-dimensional embedding spaces. Calculated as the cosine of the angle between two vectors.
            </div>
            <div>
              <strong>RAG Architecture:</strong> Combines retrieval of relevant context with generative 
              language models to produce more accurate, grounded responses.
            </div>
            <div>
              <strong>Regex-based Chunking:</strong> Uses regular expressions to identify structural boundaries 
              in documents (e.g., "Module", "Unit", "Chapter") rather than arbitrary fixed-size segments.
            </div>
            <div>
              <strong>Few-Shot Prompting:</strong> Technique where a small number of examples are provided to 
              a language model to guide its behavior on new, similar tasks.
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default References;
