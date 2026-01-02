import { useState } from 'react';
import { ExternalLink, Play, ChevronDown, ChevronRight, BookOpen, Quote } from 'lucide-react';
import { getLectureForProject } from '../../utils/lectureParser';
import type { LectureSection } from '../../utils/lectureParser';
import './ExplanationPanel.css';

interface ExplanationPanelProps {
  projectId: string;
}

export function ExplanationPanel({ projectId }: ExplanationPanelProps) {
  const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set([0]));
  const lecture = getLectureForProject(projectId);

  if (!lecture) {
    return (
      <div className="explanation-panel">
        <h3>About This Project</h3>
        <p>
          This visualization helps you understand distributed systems concepts
          through interactive simulations. Use the controls above to start,
          pause, and step through the simulation. Click on nodes to inspect
          their state or inject failures.
        </p>
      </div>
    );
  }

  const toggleSection = (index: number) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSections(newExpanded);
  };

  return (
    <div className="explanation-panel lecture-panel">
      <div className="lecture-header">
        <BookOpen size={20} />
        <h3>{lecture.title}</h3>
      </div>

      <div className="video-section">
        <a
          href={lecture.videoUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="video-link"
        >
          <div className="video-thumbnail">
            <img
              src={`https://img.youtube.com/vi/${lecture.videoId}/mqdefault.jpg`}
              alt={lecture.title}
            />
            <div className="play-overlay">
              <Play size={32} />
            </div>
          </div>
          <span className="video-text">
            Watch on YouTube
            <ExternalLink size={14} />
          </span>
        </a>
      </div>

      <div className="lecture-overview">
        <p>{lecture.overview}</p>
      </div>

      <div className="lecture-tags">
        {lecture.tags.map((tag) => (
          <span key={tag} className="tag">
            {tag}
          </span>
        ))}
      </div>

      <div className="lecture-sections">
        <h4>Key Concepts</h4>
        {lecture.sections.map((section, index) => (
          <SectionCard
            key={index}
            section={section}
            index={index}
            isExpanded={expandedSections.has(index)}
            onToggle={() => toggleSection(index)}
          />
        ))}
      </div>

      <div className="lecture-conclusion">
        <h4>Key Takeaway</h4>
        <p>{lecture.conclusion}</p>
      </div>
    </div>
  );
}

interface SectionCardProps {
  section: LectureSection;
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
}

function SectionCard({ section, isExpanded, onToggle }: SectionCardProps) {
  return (
    <div className={`section-card ${isExpanded ? 'expanded' : ''}`}>
      <button className="section-header" onClick={onToggle}>
        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <span className="section-title">{section.title}</span>
        {section.timestamp && (
          <a
            href={section.timestamp.link}
            target="_blank"
            rel="noopener noreferrer"
            className="timestamp-link"
            onClick={(e) => e.stopPropagation()}
          >
            {section.timestamp.time}
          </a>
        )}
      </button>

      {isExpanded && (
        <div className="section-content">
          <p>{section.content}</p>

          {section.quotes.length > 0 && (
            <div className="section-quotes">
              {section.quotes.map((quote, i) => (
                <blockquote key={i}>
                  <Quote size={14} />
                  <span>{quote}</span>
                </blockquote>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
