
# ⚖️ Automated Data Pipeline for Indian Legal Judgments

### Demonstrating an end-to-end workflow for acquiring, processing, and analyzing unstructured legal documents.

---

## 🎯 **Project Objective**

The goal of this project was to build a complete data pipeline to automate the extraction of structured information from raw Indian court judgment PDFs. The system is designed to handle real-world challenges like inconsistent data formats and inaccessible web sources, ultimately producing a clean, analysis-ready dataset.

---

## ⚙️ **Technical Workflow**

This project follows a three-stage pipeline, moving from raw data acquisition to final analysis.



1.  **Data Acquisition (Web Scraping):**
    * Developed a Python scraper using **`requests`** and **`BeautifulSoup`** to download judgment PDFs.
    * The script was engineered to be robust, successfully pivoting from an initially inaccessible government portal to a more stable public source (Indian Kanoon).

2.  **Data Processing (ETL):**
    * Built a parser using **`PyMuPDF`** and **Regular Expressions** to extract raw text and identify key metadata (court, case number, date) and legal sections (facts, ratio, conclusion).
    * The entire workflow is containerized in a **Jupyter Notebook** for reproducibility.

3.  **Data Cleaning & Analysis (EDA):**
    * The raw, messy output was loaded into a **`pandas`** DataFrame.
    * Conducted data cleaning to standardize formats and handle missing values (`Not Found`, `NaN`).
    * Performed Exploratory Data Analysis (EDA) to generate initial insights from the structured data.

---

##  hurdles **Challenges Faced & Solutions**

A key part of this project was overcoming real-world technical challenges.

* **Challenge 1: Inaccessible Source Website**
    * **Problem:** The initial target website (`main.sci.gov.in`) was blocking automated requests with `SSL certificate errors` and `503 Service Unavailable` errors, likely due to CAPTCHA and other anti-scraping measures.
    * **Solution:** I demonstrated agility by quickly **pivoting to an alternative source, Indian Kanoon**. I developed a new, custom scraper for this site, ensuring the project's data acquisition phase was successful.

* **Challenge 2: Messy & Inconsistent Data**
    * **Problem:** The raw extracted data was imperfect, containing many missing values and inconsistent formatting, as shown below. This is a true representation of real-world data.
    * **Solution:** I implemented a robust **data cleaning process** using `pandas` to standardize the data, handle missing values, and convert columns to their correct data types, making it suitable for analysis.


---

## 📊 **Results: From Raw Text to Actionable Insights**

After cleaning, the final dataset was used to generate meaningful insights. This demonstrates the value of transforming unstructured data into a structured format.

### Court Distribution
We can now easily visualize the distribution of judgments across different courts in our dataset.
![Bar chart showing court distribution](EDA_visuals/court_distribution.png)

### Judgments Over Time
The cleaned date information allows us to track the volume of judgments over the years.


---

## 🚀 **Future Work & Vision**

This foundational pipeline and dataset open the door for powerful Machine Learning applications:

* **Topic Modeling:** Use unsupervised learning (`LDA`, `Gensim`) on the `facts` and `ratio` columns to automatically categorize judgments by legal topic (e.g., criminal, civil, corporate).
* **Semantic Search Engine:** Index this structured data into **Elasticsearch** to build an intelligent search engine that understands legal concepts beyond simple keywords.
* **Automated Summarization:** Fine-tune a pre-trained language model (from **Hugging Face Transformers**) to generate concise summaries of long judgments.
