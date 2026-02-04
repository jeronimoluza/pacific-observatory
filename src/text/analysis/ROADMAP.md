# Extensions to News-Based Economic Monitoring System

This project extends the standard news-based Economic Policy Uncertainty (EPU) framework by constructing marginal and interaction indices that separately measure media attention to economic, policy, and uncertainty topics, as well as their pairwise intersections. All indices are constructed as **shares of all articles** and follow the same newspaper-level standardization, aggregation, and normalization procedure as the baseline EPU index.

The framework distinguishes between **breadth** (how widespread a topic is across articles) and **intensity** (how strongly a topic is emphasized within relevant articles).

---

## 1. Notation and Article Counts

For each newspaper \( n \) and time period \( t \), define:

- \( A_{n,t} \): total number of articles
- \( E_{n,t} \): number of articles containing ≥1 Economic keyword
- \( P_{n,t} \): number of articles containing ≥1 Policy keyword
- \( U_{n,t} \): number of articles containing ≥1 Uncertainty keyword

For each article \( i \):

- \( K^E_i \): number of Economic keywords in article \( i \)
- \( K^P_i \): number of Policy keywords in article \( i \)
- \( K^U_i \): number of Uncertainty keywords in article \( i \)

---

## 2. Marginal Breadth and Intensity Indices

### 2.1 Economic Attention

#### Economic Breadth (E_breadth)

\[
E^{breadth}_{n,t} = \frac{E_{n,t}}{A_{n,t}}
\]

Share of all articles that contain at least one Economic keyword. Measures the **breadth of economic coverage** in the news agenda.

#### Economic Intensity (E_intensity)

\[
E^{intensity}_{n,t} =
\frac{1}{E_{n,t}}
\sum_{i \in E_{n,t}} K^E_i
\]

Average number of Economic keywords per Economic article. Measures the **depth or intensity of economic language**, conditional on economic coverage.

---

### 2.2 Policy Attention

#### Policy Breadth (P_breadth)

\[
P^{breadth}_{n,t} = \frac{P_{n,t}}{A_{n,t}}
\]

Share of all articles that contain at least one Policy keyword. Measures the **breadth of policy coverage** in the news agenda.

#### Policy Intensity (P_intensity)

\[
P^{intensity}_{n,t} =
\frac{1}{P_{n,t}}
\sum_{i \in P_{n,t}} K^P_i
\]

Average number of Policy keywords per Policy article. Measures the **depth or intensity of policy language**, conditional on policy coverage.

---

### 2.3 Uncertainty

#### Uncertainty Breadth (U_breadth)

\[
U^{breadth}_{n,t} = \frac{U_{n,t}}{A_{n,t}}
\]

Share of all articles that contain at least one Uncertainty keyword. Measures the **breadth of uncertainty coverage** in the news agenda.

#### Uncertainty Intensity (U_intensity)

\[
U^{intensity}_{n,t} =
\frac{1}{U_{n,t}}
\sum_{i \in U_{n,t}} K^U_i
\]

Average number of Uncertainty keywords per Uncertainty article. Measures the **depth or intensity of uncertainty language**, conditional on uncertainty coverage.

---

## 3. Pairwise Interaction Indices (Shares of All Articles)

Let:

- \( (E \cap U)_{n,t} \): number of articles with ≥1 Economic AND ≥1 Uncertainty keyword
- \( (P \cap U)_{n,t} \): number of articles with ≥1 Policy AND ≥1 Uncertainty keyword
- \( (E \cap P)_{n,t} \): number of articles with ≥1 Economic AND ≥1 Policy keyword

---

### 3.1 Economic Uncertainty (E ∩ U)

\[
EU^{share}_{n,t} =
\frac{(E \cap U)_{n,t}}{A_{n,t}}
\]

Captures **economically framed uncertainty**.

---

### 3.2 Policy Uncertainty (P ∩ U)

\[
PU^{share}_{n,t} =
\frac{(P \cap U)_{n,t}}{A_{n,t}}
\]

Captures **policy-driven uncertainty**.

---

### 3.3 Economic Policy Coverage (E ∩ P)

\[
EP^{share}_{n,t} =
\frac{(E \cap P)_{n,t}}{A_{n,t}}
\]

Captures joint economic-policy coverage, regardless of uncertainty.

---

## 4. Standardization, Aggregation, and Normalization

All marginal and interaction indices follow the same procedure as the baseline EPU:

1. **Newspaper-Time Shares / Intensities**
   Compute each index at the newspaper-time level.

2. **Newspaper-Level Standardization**
   For each newspaper \( n \) and index \( X \), compute:
   \[
   Z^X_{n,t} = \frac{X_{n,t} - \mu^X_n}{\sigma^X_n}
   \]
   where \( \mu^X_n \) and \( \sigma^X_n \) are computed over a fixed reference period.

3. **Aggregation Across Newspapers**
   Aggregate by averaging standardized values across newspapers:
   \[
   Z^X_t = \frac{1}{N_t} \sum_n Z^X_{n,t}
   \]

4. **Normalization**
   Rescale aggregated indices to a common baseline (e.g., mean = 100 over a reference period).

---

## 5. Relationship to Standard EPU

The standard EPU index corresponds to:

\[
EPU_{n,t} =
\frac{(E \cap P \cap U)_{n,t}}{A_{n,t}}
\]

The extended framework allows full decomposition of EPU movements into:

- Economic breadth and intensity (E_breadth, E_intensity)
- Policy breadth and intensity (P_breadth, P_intensity)
- Uncertainty breadth and intensity (U_breadth, U_intensity)
- Economically framed uncertainty (E ∩ U)
- Policy-driven uncertainty (P ∩ U)
- Economic policy coverage (E ∩ P)
