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

## 6. Topic- / Actor-Conditioned Uncertainty (Attribution)

To attribute sources of media-reported uncertainty to specific institutions, actors, or thematic domains, the framework is extended to construct **topic- and actor-conditioned uncertainty indices**. These indices measure the extent to which uncertainty coverage is associated with particular groups \( g \), where \( g \) may represent:

- International institutions (e.g., IMF, World Bank)
- Domestic institutions (e.g., central bank, government, parliament)
- Thematic domains (e.g., inflation, labor, climate, public debt)

This extension allows decomposition of aggregate uncertainty into institution- and topic-specific components, while remaining fully consistent with the shares-of-all-articles construction used throughout the system.

---

### 6.A Formal Definition (Consistent with the Core System)

For any actor or topic group \( g \), define:

- \( G_{n,t} \): number of articles containing ≥1 keyword for group \( g \)

- \( (U \cap G)_{n,t} \): number of articles containing:
  - ≥1 Uncertainty keyword
  - AND ≥1 keyword for group \( g \)

---

### 6.B Absolute Conditioned Uncertainty (Agenda-Based)

#### Actor/Topic-Conditioned Uncertainty Share

\[
U^{g,\,share}_{n,t}
=
\frac{(U \cap G)_{n,t}}{A_{n,t}}
\]

This measures:

> The share of all news devoted to uncertainty related to actor or topic \( g \).

This definition is fully consistent with the use of **shares of all articles** across the extended EPU framework.

Examples:

- \( U^{IMF,\,share}_{n,t} \): IMF-conditioned uncertainty
- \( U^{CB,\,share}_{n,t} \): central bank–conditioned uncertainty
- \( U^{Inflation,\,share}_{n,t} \): inflation-conditioned uncertainty
- \( U^{Labor,\,share}_{n,t} \): labor-conditioned uncertainty

These indices capture how salient each actor or topic is within the overall uncertainty-related news agenda.

---

### 6.C Framing-Based Version (Composition of Uncertainty)

In addition to agenda-based attribution, a framing-based version will be constructed:

\[
U^{g \mid U}_{n,t}
=
\frac{(U \cap G)_{n,t}}{U_{n,t}}
\]

This measures:

> Among all uncertainty-related articles, the fraction attributable to actor or topic \( g \).

This is a **composition / framing attribution** measure, indicating how uncertainty is being framed across different actors or themes.

While not required for headline indices, this measure is analytically valuable for:

- Decomposing the sources of uncertainty
- Identifying shifts in the institutional or thematic framing of uncertainty
- Distinguishing between changes in overall uncertainty vs changes in what uncertainty is about

---

### 6.D Standardization, Aggregation, and Normalization

Both agenda-based and framing-based conditioned uncertainty measures follow the same procedure as all other indices:

1. Compute newspaper-time values
2. Standardize by newspaper over a fixed reference period
3. Aggregate standardized values across newspapers
4. Normalize to a common baseline

This ensures full comparability with:

- Aggregate uncertainty (U_breadth, U_intensity)
- Economic and policy uncertainty (EU, PU)
- Actor- and topic-conditioned uncertainty (\( U \cap G \))
