export function formatSimilarityScore(score) {
  return (score * 100).toFixed(1);
}

export function formatSyllabusMetadata(metadata) {
  return `${metadata.department} - ${metadata.program} - Sem ${metadata.semester} - ${metadata.subject_name}`;
}

export function truncateText(text, maxLength = 100) {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

export function getDecisionBadgeClass(isInSyllabus) {
  return isInSyllabus
    ? 'bg-green-100 text-green-800 border-green-300'
    : 'bg-red-100 text-red-800 border-red-300';
}

export function getDecisionLabel(isInSyllabus) {
  return isInSyllabus ? 'In Syllabus' : 'Out of Syllabus';
}
