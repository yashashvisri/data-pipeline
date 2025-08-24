### **Manually Collecting Data**

The project began with a crucial prototyping phase to understand the problem space before building a large-scale, automated solution.

#### **Process**
1.  **Manual Data Collection:** I started by manually downloading a curated set of **10 sample judgment PDFs** from official sources like the Supreme Court of India portal. This ensured a representative mix of document layouts.

2.  **Interactive Exploration:** The entire prototyping process was conducted within a **Jupyter Notebook**. This interactive environment was essential for rapidly testing text extraction logic and iterating on regular expression patterns for metadata parsing.
    

3.  **Core Logic Development:** I developed the initial Python script using **`PyMuPDF`** to read PDF files and **Regular Expressions (Regex)** to locate and extract specific metadata fields (e.g., court, case number, date) and key legal sections.

#### **Key Findings from Prototyping**
This initial phase was critical for uncovering real-world data challenges that directly informed the design of the final pipeline:

* **Finding 1: The "Scanned PDF" Problem:** A key discovery was that **50% of the sample documents were scanned images**, not text-based PDFs. My script correctly identified these as unreadable, highlighting a major obstacle that any scalable solution must overcome with technology like OCR.

* **Finding 2: Inconsistent Formatting:** No two judgments were formatted identically. I documented significant variations in how dates were written, parties were listed, and sections were titled. This proved that a rigid, purely rule-based system would be too fragile for a production environment and requires a more intelligent parsing approach.

* **Finding 3: Validation of Core Tools:** This phase successfully validated that the chosen technology stack (`Python`, `PyMuPDF`, `pandas`) was effective for the core task of parsing native text-based PDFs.
