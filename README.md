## Started with collecting data from different data sources
#### 💾 **Data Sources**

The raw PDF documents for this project were acquired by scraping the following publicly available sources:

* **Primary Source:** [**Indian Kanoon**](https://indiankanoon.org/) - Used for downloading the final set of judgment documents due to its stability and accessibility.
* **Initial Target:** [**Supreme Court of India Judgments Portal**](https://main.sci.gov.in/judgments) - The initial data source, which was later replaced due to technical challenges (expired SSL certificate and anti-scraping measures).


## 💾 **Data Acquisition: A Two-Phase Approach**

To ensure a robust and scalable pipeline, I approached data collection in two distinct phases: manual collection for initial prototyping and automated scraping for building a larger dataset.

### **Phase 1: Manual Collection for Prototyping**
* **Method:** I began by manually downloading a curated set of 10 sample judgment PDFs from various sources like the Supreme Court of India portal and e-Courts.
* **Purpose:** This initial, small-scale collection was crucial for understanding the document structure, identifying key challenges (like scanned vs. native PDFs), and developing the core parsing logic for the data pipeline.

### **Phase 2: Automated Scraping for Scalability**
* **Method:** Once the pipeline was proven effective, I developed an automated web scraper using Python's **`requests`** and **`BeautifulSoup`** libraries.
* **Purpose:** This scraper was designed to programmatically download a larger corpus of documents from a stable public source ([Indian Kanoon](https://indiankanoon.org/)). This step demonstrated the scalability of the project and allowed for the creation of the final, more comprehensive dataset used for analysis.
