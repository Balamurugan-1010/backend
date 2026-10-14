import re
from typing import List, Set, Dict

# Comprehensive Skill Alias & Normalization Mapping
SKILL_NORMALIZATION_MAP: Dict[str, str] = {
    # Web & Frontend
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ecmascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "svelte": "Svelte",
    "redux": "Redux",

    # Backend & Frameworks
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "express": "Express.js",
    "expressjs": "Express.js",
    "express.js": "Express.js",
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "spring": "Spring Boot",
    "springboot": "Spring Boot",
    "spring boot": "Spring Boot",
    "dotnet": ".NET",
    ".net": ".NET",
    "asp.net": "ASP.NET",
    "ruby on rails": "Ruby on Rails",
    "rails": "Ruby on Rails",
    "rest": "REST API",
    "rest api": "REST API",
    "restful": "REST API",
    "graphql": "GraphQL",

    # Programming Languages
    "python": "Python",
    "python3": "Python",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "php": "PHP",
    "ruby": "Ruby",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "scala": "Scala",
    "dart": "Dart",

    # Databases
    "mysql": "MySQL",
    "my sql": "MySQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "psql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "sqlite": "SQLite",
    "redis": "Redis",
    "oracle": "Oracle DB",
    "cassandra": "Cassandra",
    "dynamodb": "DynamoDB",
    "elasticsearch": "Elasticsearch",
    "sql": "SQL",

    # Machine Learning & AI
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "dl": "Deep Learning",
    "deep learning": "Deep Learning",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "cv": "Computer Vision",
    "computer vision": "Computer Vision",
    "tensorflow": "TensorFlow",
    "tf": "TensorFlow",
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    "scikit-learn": "Scikit-Learn",
    "scikitlearn": "Scikit-Learn",
    "sklearn": "Scikit-Learn",
    "keras": "Keras",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scipy": "SciPy",
    "opencv": "OpenCV",
    "huggingface": "Hugging Face",
    "hugging face": "Hugging Face",
    "llm": "LLMs",
    "llms": "LLMs",
    "genai": "Generative AI",
    "generative ai": "Generative AI",

    # Cloud & DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "gcp": "Google Cloud",
    "google cloud": "Google Cloud",
    "docker": "Docker",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "jenkins": "Jenkins",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "linux": "Linux",
    "terraform": "Terraform",
    "ansible": "Ansible",

    # Mobile
    "android": "Android",
    "ios": "iOS",
    "react native": "React Native",
    "reactnative": "React Native",
    "flutter": "Flutter",

    # QA & Testing
    "selenium": "Selenium",
    "cypress": "Cypress",
    "jest": "Jest",
    "pytest": "PyTest",
    "unit testing": "Unit Testing",
    "agile": "Agile",
    "scrum": "Scrum",
    "jira": "Jira"
}

# Canonical Skills Catalog
CANONICAL_SKILLS: Set[str] = set(SKILL_NORMALIZATION_MAP.values())

def normalize_skill(skill: str) -> str:
    """Normalize any skill string to its canonical industry standard representation."""
    if not skill:
        return ""
    cleaned = skill.strip().lower()
    # Check direct normalization map
    if cleaned in SKILL_NORMALIZATION_MAP:
        return SKILL_NORMALIZATION_MAP[cleaned]
    # Check if exact casing matches a canonical skill
    for canonical in CANONICAL_SKILLS:
        if canonical.lower() == cleaned:
            return canonical
    # Return formatted title case as fallback
    return skill.strip().title()

def extract_skills_from_text(text: str) -> List[str]:
    """
    Extract technical skills from freeform resume or job description text
    using word boundary regex patterns and dictionary lookups.
    """
    if not text:
        return []
    
    found_skills: Set[str] = set()
    lowered_text = text.lower()

    # Sort aliases by descending length to match longer phrases first (e.g. "machine learning" before "ml")
    sorted_aliases = sorted(SKILL_NORMALIZATION_MAP.keys(), key=len, reverse=True)

    for alias in sorted_aliases:
        # Special boundary handling for symbols like c++, c#, .net
        if alias in ["c++", "c#", ".net"]:
            escaped = re.escape(alias)
            pattern = rf"(?:^|[\s,;:(/]){escaped}(?:[\s,;:)/]|$)"
        elif len(alias) <= 2:
            # Short aliases like "go", "js", "ts", "ml", "dl", "cv", "r" require strict word boundaries
            escaped = re.escape(alias)
            pattern = rf"\b{escaped}\b"
        else:
            escaped = re.escape(alias)
            pattern = rf"\b{escaped}\b"

        if re.search(pattern, lowered_text):
            found_skills.add(SKILL_NORMALIZATION_MAP[alias])

    return sorted(list(found_skills))
