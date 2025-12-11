import React from 'react';
import SectionHeader from '../components/common/SectionHeader';
import Card from '../components/common/Card';

function About() {
  const teamMembers = [
    {
      name: 'Student Name 1',
      role: 'Lead Developer',
      contributions: 'RAG architecture design, SBERT integration, system implementation',
    },
    {
      name: 'Student Name 2',
      role: 'ML Engineer',
      contributions: 'LLM validation module, few-shot prompting strategy, experimental evaluation',
    },
    {
      name: 'Student Name 3',
      role: 'Full-Stack Developer',
      contributions: 'Frontend interface, API design, ChromaDB integration',
    },
    {
      name: 'Student Name 4',
      role: 'Data Engineer',
      contributions: 'Syllabus preprocessing, chunking algorithms, dataset curation',
    },
  ];

  const mentors = [
    {
      name: 'Dr. [Mentor Name]',
      designation: 'Project Guide',
      department: 'Department of Information Technology',
    },
    {
      name: 'Prof. [Co-Guide Name]',
      designation: 'Co-Guide',
      department: 'Department of Information Technology',
    },
  ];

  return (
    <div className="section-container">
      <SectionHeader
        title="About the Project"
        subtitle="Team, institution, and project context"
      />

      <div className="max-w-5xl mx-auto space-y-8">
        {/* Project Context */}
        <Card>
          <h3 className="text-2xl font-semibold mb-4">Project Information</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-gray-700">
            <div>
              <div className="font-semibold text-gray-900 mb-1">Project Title</div>
              <div>RAG-Based Semantic Question Analyzer for Syllabus Relevance Verification</div>
            </div>
            <div>
              <div className="font-semibold text-gray-900 mb-1">Academic Year</div>
              <div>2024-2025</div>
            </div>
            <div>
              <div className="font-semibold text-gray-900 mb-1">Department</div>
              <div>Information Technology</div>
            </div>
            <div>
              <div className="font-semibold text-gray-900 mb-1">Program</div>
              <div>Bachelor of Technology (B.Tech)</div>
            </div>
            <div>
              <div className="font-semibold text-gray-900 mb-1">Institution</div>
              <div>[University/College Name]</div>
            </div>
            <div>
              <div className="font-semibold text-gray-900 mb-1">Project Type</div>
              <div>Final Year Major Project</div>
            </div>
          </div>
        </Card>

        {/* Team Members */}
        <Card>
          <h3 className="text-2xl font-semibold mb-6">Team Members</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {teamMembers.map((member, idx) => (
              <div key={idx} className="p-5 bg-gradient-to-br from-primary-50 to-accent-50 rounded-lg border border-primary-200">
                <div className="flex items-center space-x-3 mb-3">
                  <div className="w-12 h-12 bg-gradient-to-br from-primary-500 to-accent-500 rounded-full flex items-center justify-center text-white font-bold text-lg">
                    {member.name.charAt(0)}
                  </div>
                  <div>
                    <div className="font-semibold text-gray-900">{member.name}</div>
                    <div className="text-sm text-primary-700">{member.role}</div>
                  </div>
                </div>
                <div className="text-sm text-gray-700">{member.contributions}</div>
              </div>
            ))}
          </div>
        </Card>

        {/* Mentors */}
        <Card>
          <h3 className="text-2xl font-semibold mb-6">Project Mentors</h3>
          <div className="space-y-4">
            {mentors.map((mentor, idx) => (
              <div key={idx} className="p-5 bg-gray-50 rounded-lg border border-gray-200">
                <div className="font-semibold text-gray-900 text-lg">{mentor.name}</div>
                <div className="text-sm text-primary-700 mb-1">{mentor.designation}</div>
                <div className="text-sm text-gray-600">{mentor.department}</div>
              </div>
            ))}
          </div>
        </Card>

        {/* Project Motivation */}
        <Card className="bg-gradient-to-br from-primary-50 to-accent-50 border-primary-200">
          <h3 className="text-2xl font-semibold mb-4">Motivation & Vision</h3>
          <div className="space-y-4 text-gray-700">
            <p className="leading-relaxed">
              This project was initiated to address a real-world challenge faced by educational institutions: 
              ensuring fairness and accuracy in academic assessments through automated syllabus verification.
            </p>
            <p className="leading-relaxed">
              Our vision extends beyond engineering education. We aim to create a scalable, domain-agnostic 
              system that can serve entire universities, reducing manual workload for educators while improving 
              assessment quality and consistency for students.
            </p>
            <p className="leading-relaxed">
              By combining state-of-the-art NLP techniques (RAG, SBERT, LLM validation) with practical 
              cost-optimization strategies (the Cosine Gatekeeper), we've developed a system that is both 
              intelligent and deployable at scale.
            </p>
          </div>
        </Card>

        {/* Acknowledgments */}
        <Card>
          <h3 className="text-2xl font-semibold mb-4">Acknowledgments</h3>
          <div className="text-gray-700 space-y-3">
            <p>
              We would like to express our sincere gratitude to our project guides for their invaluable 
              guidance, support, and feedback throughout the development of this project.
            </p>
            <p>
              We also thank the Department of Information Technology and our institution for providing 
              the necessary resources and infrastructure to conduct this research.
            </p>
            <p>
              Special thanks to the open-source community for developing the tools and models that made 
              this project possible: Sentence-Transformers, ChromaDB, Hugging Face, and many others.
            </p>
          </div>
        </Card>

        {/* Contact */}
        <Card>
          <h3 className="text-2xl font-semibold mb-4">Contact & Future Collaboration</h3>
          <p className="text-gray-700 mb-4">
            For inquiries about this project, potential collaboration, or deployment opportunities, 
            please contact:
          </p>
          <div className="text-gray-700">
            <div className="mb-2">
              <strong>Email:</strong> [project-email@university.edu]
            </div>
            <div className="mb-2">
              <strong>Department:</strong> Information Technology, [University Name]
            </div>
            <div>
              <strong>GitHub:</strong> [Repository link - if applicable]
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default About;
