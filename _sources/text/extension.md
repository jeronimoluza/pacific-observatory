# Extended News-Based Economic Monitoring

This section extends the standard Economic Policy Uncertainty (EPU) framework by constructing additional indices that separately measure media attention to economic, policy, and uncertainty topics, as well as their pairwise intersections and attribution to specific actors or themes.

## From EPU to Breadth and Intensity

The standard EPU index measures the share of articles containing keywords from all three categories (Economic, Policy, and Uncertainty). This can be understood as a **breadth** measure—how widespread is the joint coverage of these topics across the news agenda.

The extended framework generalizes this concept by:
1. **Marginal Breadth Indices**: Measuring each topic category independently
2. **Intensity Indices**: Measuring how deeply each topic is covered within relevant articles
3. **Pairwise Interaction Indices**: Measuring overlaps between any two categories
4. **Uncertainty Attribution**: Decomposing uncertainty by topic or institutional source

All indices follow the same standardization, aggregation, and normalization procedure as the baseline EPU index.

---

## Marginal Breadth Indices

Breadth indices measure the **share of all articles** that contain at least one keyword from a given category. This captures how widespread a topic is across the news agenda.

### Notation

For each newspaper $n$ and time period $t$:
- $A_{n,t}$: total number of articles
- $E_{n,t}$: number of articles containing ≥1 Economic keyword
- $P_{n,t}$: number of articles containing ≥1 Policy keyword
- $U_{n,t}$: number of articles containing ≥1 Uncertainty keyword

### Economic Breadth

$$
E^{breadth}_{n,t} = \frac{E_{n,t}}{A_{n,t}}
$$

Share of all articles that contain at least one Economic keyword. Measures the **breadth of economic coverage** in the news agenda.

### Policy Breadth

$$
P^{breadth}_{n,t} = \frac{P_{n,t}}{A_{n,t}}
$$

Share of all articles that contain at least one Policy keyword. Measures the **breadth of policy coverage** in the news agenda.

### Uncertainty Breadth

$$
U^{breadth}_{n,t} = \frac{U_{n,t}}{A_{n,t}}
$$

Share of all articles that contain at least one Uncertainty keyword. Measures the **breadth of uncertainty coverage** in the news agenda.

<div style="display:flex;justify-content:flex-start;width:950px;margin-bottom:4px;">
  <a href="../interactive/text/breadth_pic.html" target="_blank" style="font-size:0.8em;padding:3px 10px;border:1px solid #667eea;border-radius:4px;color:#667eea;text-decoration:none;">&#x2197; Open in new tab</a>
</div>
<div>
<iframe src="../interactive/text/breadth_pic.html"
frameborder="0" marginwidth="0" marginheight="0" width="950" height="500"></iframe>
</div>

---

## Marginal Intensity Indices

While breadth measures how widespread a topic is, **intensity** measures how deeply a topic is covered within relevant articles. Intensity is defined as the average number of keywords per article, conditional on the article containing at least one keyword from that category.

### Notation

For each article $i$:
- $K^E_i$: number of Economic keywords in article $i$
- $K^P_i$: number of Policy keywords in article $i$
- $K^U_i$: number of Uncertainty keywords in article $i$

### Economic Intensity

$$
E^{intensity}_{n,t} = \frac{1}{E_{n,t}} \sum_{i \in E_{n,t}} K^E_i
$$

Average number of Economic keywords per Economic article. Measures the **depth of economic language**, conditional on economic coverage.

### Policy Intensity

$$
P^{intensity}_{n,t} = \frac{1}{P_{n,t}} \sum_{i \in P_{n,t}} K^P_i
$$

Average number of Policy keywords per Policy article. Measures the **depth of policy language**, conditional on policy coverage.

### Uncertainty Intensity

$$
U^{intensity}_{n,t} = \frac{1}{U_{n,t}} \sum_{i \in U_{n,t}} K^U_i
$$

Average number of Uncertainty keywords per Uncertainty article. Measures the **depth of uncertainty language**, conditional on uncertainty coverage.

<div style="display:flex;justify-content:flex-start;width:950px;margin-bottom:4px;">
  <a href="../interactive/text/intensity_pic.html" target="_blank" style="font-size:0.8em;padding:3px 10px;border:1px solid #667eea;border-radius:4px;color:#667eea;text-decoration:none;">&#x2197; Open in new tab</a>
</div>
<div>
<iframe src="../interactive/text/intensity_pic.html"
frameborder="0" marginwidth="0" marginheight="0" width="950" height="500"></iframe>
</div>

---

## Pairwise Interaction Indices

The standard EPU requires articles to contain keywords from all three categories. The pairwise interaction indices relax this requirement, measuring the share of articles that contain keywords from any two categories.

### Notation

- $(E \cap U)_{n,t}$: number of articles with ≥1 Economic AND ≥1 Uncertainty keyword
- $(P \cap U)_{n,t}$: number of articles with ≥1 Policy AND ≥1 Uncertainty keyword
- $(E \cap P)_{n,t}$: number of articles with ≥1 Economic AND ≥1 Policy keyword

### Economic-Uncertainty (EU)

$$
EU^{share}_{n,t} = \frac{(E \cap U)_{n,t}}{A_{n,t}}
$$

Captures **economically framed uncertainty**—uncertainty that is discussed in an economic context, regardless of policy mentions.

### Policy-Uncertainty (PU)

$$
PU^{share}_{n,t} = \frac{(P \cap U)_{n,t}}{A_{n,t}}
$$

Captures **policy-driven uncertainty**—uncertainty that is discussed in a policy context, regardless of economic mentions.

### Economic-Policy (EP)

$$
EP^{share}_{n,t} = \frac{(E \cap P)_{n,t}}{A_{n,t}}
$$

Captures **joint economic-policy coverage**—articles discussing both economic and policy topics, regardless of uncertainty.

<div style="display:flex;justify-content:flex-start;width:950px;margin-bottom:4px;">
  <a href="../interactive/text/pairwise_pic.html" target="_blank" style="font-size:0.8em;padding:3px 10px;border:1px solid #667eea;border-radius:4px;color:#667eea;text-decoration:none;">&#x2197; Open in new tab</a>
</div>
<div>
<iframe src="../interactive/text/pairwise_pic.html"
frameborder="0" marginwidth="0" marginheight="0" width="950" height="500"></iframe>
</div>

---

## Uncertainty Attribution

To understand **what** uncertainty is about, the framework extends to construct topic- and actor-conditioned uncertainty indices. These measure the extent to which uncertainty coverage is associated with specific themes or institutions.

### Topic-Conditioned Uncertainty

For any topic group $g$ (e.g., inflation, labor, climate, trade), define:
- $G_{n,t}$: number of articles containing ≥1 keyword for topic $g$
- $(U \cap G)_{n,t}$: number of articles containing ≥1 Uncertainty keyword AND ≥1 keyword for topic $g$

#### Agenda-Based Attribution

$$
U^{g,\,share}_{n,t} = \frac{(U \cap G)_{n,t}}{A_{n,t}}
$$

The share of all news devoted to uncertainty related to topic $g$. This measures how salient each topic is within the overall uncertainty-related news agenda.

#### Framing-Based Attribution

$$
U^{g \mid U}_{n,t} = \frac{(U \cap G)_{n,t}}{U_{n,t}}
$$

Among all uncertainty-related articles, the fraction attributable to topic $g$. This is a **composition measure**, indicating how uncertainty is being framed across different themes.

<div style="display:flex;justify-content:flex-start;width:950px;margin-bottom:4px;">
  <a href="../interactive/text/topic_attribution_pic.html" target="_blank" style="font-size:0.8em;padding:3px 10px;border:1px solid #667eea;border-radius:4px;color:#667eea;text-decoration:none;">&#x2197; Open in new tab</a>
</div>
<div>
<iframe src="../interactive/text/topic_attribution_pic.html"
frameborder="0" marginwidth="0" marginheight="0" width="950" height="475"></iframe>
</div>

### Actor-Conditioned Uncertainty

The same framework applies to institutional actors (e.g., IMF, World Bank, central bank, government, parliament):

#### Agenda-Based Attribution

$$
U^{actor,\,share}_{n,t} = \frac{(U \cap Actor)_{n,t}}{A_{n,t}}
$$

The share of all news devoted to uncertainty related to a specific actor.

#### Framing-Based Attribution

$$
U^{actor \mid U}_{n,t} = \frac{(U \cap Actor)_{n,t}}{U_{n,t}}
$$

Among all uncertainty-related articles, the fraction attributable to a specific actor.

<div style="display:flex;justify-content:flex-start;width:950px;margin-bottom:4px;">
  <a href="../interactive/text/actor_attribution_pic.html" target="_blank" style="font-size:0.8em;padding:3px 10px;border:1px solid #667eea;border-radius:4px;color:#667eea;text-decoration:none;">&#x2197; Open in new tab</a>
</div>
<div>
<iframe src="../interactive/text/actor_attribution_pic.html"
frameborder="0" marginwidth="0" marginheight="0" width="950" height="475"></iframe>
</div>

---

## Standardization and Normalization

All indices follow the same procedure as the baseline EPU:

1. **Newspaper-Time Shares**: Compute each index at the newspaper-time level

2. **Newspaper-Level Standardization**: For each newspaper $n$ and index $X$:

   $$
   Z^X_{n,t} = \frac{X_{n,t} - \mu^X_n}{\sigma^X_n}
   $$

   where $\mu^X_n$ and $\sigma^X_n$ are computed over a fixed reference period

3. **Aggregation**: Average standardized values across newspapers:

   $$
   Z^X_t = \frac{1}{N_t} \sum_n Z^X_{n,t}
   $$

4. **Normalization**: Rescale to a common baseline (mean = 100 over the reference period)

This ensures all indices are comparable and can be analyzed together.

---

## Relationship to Standard EPU

The standard EPU index corresponds to:

$$
EPU_{n,t} = \frac{(E \cap P \cap U)_{n,t}}{A_{n,t}}
$$

The extended framework allows full decomposition of EPU movements into:
- **Marginal effects**: Changes in economic, policy, or uncertainty coverage independently
- **Pairwise interactions**: Changes in how topics co-occur
- **Attribution**: Changes in what uncertainty is about (topics and actors)

This decomposition helps distinguish between, for example:
- A general increase in uncertainty coverage vs. uncertainty specifically about inflation
- Broad policy uncertainty vs. uncertainty attributed to specific institutions
- Changes in the overall news agenda vs. changes in how uncertainty is framed
