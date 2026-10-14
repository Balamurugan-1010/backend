import re
from typing import Dict, List

# Basic common English stopwords
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
    "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself",
    "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into",
    "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's",
    "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs",
    "them", "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't",
    "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself",
    "yourselves"
}

def clean_text(text: str) -> str:
    """
    Cleans raw text while preserving technology symbols (like C++, C#, .NET).
    """
    if not text:
        return ""
    # Remove URLs and email addresses
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", " ", text)
    # Normalize unicode/non-ascii characters
    text = text.encode("ascii", "ignore").decode()
    # Normalize whitespaces and newlines
    text = re.sub(r"[\r\n\t]+", " ", text)
    # Remove non-alphanumeric except for +, #, ., / which are common in tech names
    text = re.sub(r"[^a-zA-Z0-9\s+#./-]", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text

def preprocess_for_tfidf(text: str) -> str:
    """
    Cleans, lowercases, and removes stopwords for TF-IDF vectorization.
    """
    cleaned = clean_text(text).lower()
    tokens = cleaned.split()
    filtered_tokens = [tok for tok in tokens if tok not in STOPWORDS and len(tok) > 1]
    return " ".join(filtered_tokens)

def parse_resume_sections(raw_text: str) -> Dict[str, str]:
    """
    Heuristically segment resume text into typical sections:
    education, projects, internship/experience, certifications.
    """
    sections = {
        "education": "",
        "projects": "",
        "experience": "",
        "certifications": "",
        "full_text": clean_text(raw_text)
    }

    if not raw_text:
        return sections

    lines = raw_text.splitlines()
    current_section = "general"
    section_buffers: Dict[str, List[str]] = {
        "education": [],
        "projects": [],
        "experience": [],
        "certifications": [],
        "general": []
    }

    section_keywords = {
        "education": ["education", "academic", "academics", "qualifications", "degree"],
        "projects": ["projects", "academic projects", "key projects", "personal projects"],
        "experience": ["experience", "internship", "internships", "work experience", "employment"],
        "certifications": ["certifications", "certificate", "certificates", "courses", "licenses"]
    }

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower_line = stripped.lower()

        # Check if line looks like a header (short length, keywords)
        matched_header = None
        if len(stripped.split()) <= 4:
            for sec_name, keywords in section_keywords.items():
                if any(lower_line == kw or lower_line.startswith(kw + ":") for kw in keywords):
                    matched_header = sec_name
                    break

        if matched_header:
            current_section = matched_header
        else:
            section_buffers[current_section].append(stripped)

    sections["education"] = " ".join(section_buffers["education"])
    sections["projects"] = " ".join(section_buffers["projects"])
    sections["experience"] = " ".join(section_buffers["experience"])
    sections["certifications"] = " ".join(section_buffers["certifications"])

    return sections
