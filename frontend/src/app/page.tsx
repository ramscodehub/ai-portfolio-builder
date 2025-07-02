"use client";

import { useState, FormEvent, useEffect } from "react";
import styles from "./DarkHomePage.module.css"; 

// --- Icons and Interfaces (as before) ---
const AiIconPlaceholder = () => ( <div style={{ width: '28px', height: '28px', background: 'linear-gradient(135deg, #BB86FC, #6200EE)', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '14px' }}>AI</div> );
interface GalleryItem { id: string; viewLink: string; category: string; title: string; description?: string; }
interface CloneApiResponse { message: string; file_path: string; view_link?: string; }

// --- Static Gallery Data (as before) ---
const allGalleryItems: GalleryItem[] = [
    { id: "ola", viewLink: "/generated_html_clones/clone_www_olacabs_com_20250605_183343.html", category: "Landing Pages", title: "Ola Cabs", description: "Ride Hailing Service" },
    { id: "lyft", viewLink: "/generated_html_clones/clone_www_lyft_com_20250606_162527.html", category: "Landing Pages", title: "Lyft.com", description: "Rideshare Service" },
    { id: "fitness", viewLink: "/generated_html_clones/clone_fittrack-landing-page-smoky_vercel_app_20250606_151340.html", category: "Landing Pages", title: "FitTrack", description: "Fitness Platform"},
    { id: "wix", viewLink: "/generated_html_clones/clone_www_wix_com_20250605_190834.html", category: "Landing Pages", title: "Wix.com", description: "Website Builder" },
    { id: "wordpress", viewLink: "/generated_html_clones/clone_wordpress_com_20250605_222253.html", category: "Landing Pages", title: "WordPress.com", description: "Blogging Platform" },
    { id: "simplegreet", viewLink: "/generated_html_clones/clone_simple-greetings-1748253405653_vercel_app_20250605_193006.html", category: "Landing Pages", title: "Simple Greetings", description: "Portfolio Example" },
    { id: "uber", viewLink: "/generated_html_clones/clone_www_uber_com_20250605_175014.html", category: "Landing Pages", title: "Uber.com", description: "Ride & Delivery" },
];

export default function HomePage() {
  const [referenceUrl, setReferenceUrl] = useState<string>("");
  const [resumeText, setResumeText] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [showUnoLink, setShowUnoLink] = useState<boolean>(false);
  
  const [filteredGalleryItems, setFilteredGalleryItems] = useState<GalleryItem[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("Landing Pages"); 

  const categories = ["Landing Pages", "All"];
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  useEffect(() => {
    if (activeCategory === "All") { setFilteredGalleryItems(allGalleryItems); } 
    else { setFilteredGalleryItems(allGalleryItems.filter(item => item.category === activeCategory)); }
  }, [activeCategory]); 

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!referenceUrl) { setError("Please enter a reference portfolio URL."); return; }
    if (!resumeText) { setError("Please paste your resume information."); return; }
    
    setIsLoading(true); setError(null); 
    setStatusMessage("Building your portfolio... This may take 4-5 minutes.");
    setShowUnoLink(true);

    const payload = { reference_url: referenceUrl, resume_text: resumeText };

    try {
        const response = await fetch(`${BACKEND_URL}/build-portfolio`, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        
        if (!response.ok) {
            let errorDetail = `Error: ${response.status} ${response.statusText}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; }
            catch (e) { /* Ignore */ }
            throw new Error(errorDetail);
        }
        const data: CloneApiResponse = await response.json();
        
        setShowUnoLink(false);
        setStatusMessage(data.message || "Portfolio built successfully!");

        if (data.view_link) {
            window.open(data.view_link, '_blank', 'noopener,noreferrer');
        } else {
            setError("Portfolio built successfully, but no viewable link was returned.");
        }
    } catch (err: any) {
        setError(err.message || "Failed to build portfolio.");
        setStatusMessage("Portfolio building process failed.");
        setShowUnoLink(false);
        console.error("API Error:", err);
    } finally {
        setIsLoading(false);
    }
  };
  
  const handleGalleryCardClick = (viewLink: string) => {
    window.open(viewLink, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className={styles.mainContainer}>
      <header className={styles.header}>
        <div className={styles.logoContainer}> <AiIconPlaceholder /> </div>
      </header>

      <section className={styles.heroSection}>
        <h1 className={styles.heroHeadline}>Build your portfolio in seconds</h1>
        <p className={styles.heroSubHeadline}>
          Provide a reference portfolio for style, and your resume for content.
        </p>
        
        <form onSubmit={handleSubmit} className={styles.inputForm}>
          
          <div className={styles.inputCard}>
            <label htmlFor="referenceUrl" className={styles.inputLabel}>
              Reference Portfolio URL
            </label>
            <input
              id="referenceUrl"
              type="url"
              value={referenceUrl}
              onChange={(e) => setReferenceUrl(e.target.value)}
              placeholder="https://www.example-portfolio.com"
              className={styles.urlInput}
              required
              disabled={isLoading}
            />
          </div>

          <div className={styles.inputCard}>
            <label htmlFor="resumeText" className={styles.inputLabel}>
              Your Resume / Profile Info
            </label>
            <textarea
              id="resumeText"
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder="Paste your full resume or professional bio here..."
              className={styles.resumeTextarea}
              required
              disabled={isLoading}
            />
          </div>

          <div className={styles.submitButtonContainer}>
            <button type="submit" className={styles.submitButton} disabled={isLoading} aria-label="Build Portfolio">
              <span>Build My Portfolio</span>
            </button>
          </div>
        </form>
      </section>

      {/* --- Status messages and Gallery sections (as before) --- */}
      {(isLoading || statusMessage || error) && ( <div className={styles.statusMessageContainer}> {isLoading && statusMessage && <p className={styles.statusMessage}>{statusMessage}</p>} {isLoading && showUnoLink && ( <p className={styles.unoLinkMessage}> While you wait, feel free to play a game of <a href="https://unoapp-qpfg65xn6a-ue.a.run.app/" target="_blank" rel="noopener noreferrer" className={styles.unoLink}>UNO that I built!</a> </p> )} {!isLoading && statusMessage && !error && <p className={styles.statusMessage}>{statusMessage}</p>} {error && <p className={styles.errorMessage}>{error}</p>} </div> )}
      <section className={styles.gallerySection}> <h2 className={styles.galleryMainTitle}>Example Portfolios & Styles</h2> <p className={styles.gallerySubTitle}>Click any card to visit the live site</p> <div className={styles.categoryButtons}> {categories.map((category) => ( <button key={category} className={`${styles.categoryButton} ${activeCategory === category ? styles.active : ''}`} onClick={() => setActiveCategory(category)}> {category} </button> ))} </div> <div className={styles.galleryGrid}> {filteredGalleryItems.map((site) => ( <div key={site.id} className={styles.galleryCard} onClick={() => handleGalleryCardClick(site.viewLink)} style={{ cursor: 'pointer' }}> <div className={styles.galleryCardPreviewContainer}> <iframe src={site.viewLink} className={styles.galleryCardPreview} title={`Preview of ${site.title}`} sandbox="allow-scripts allow-same-origin" scrolling="no" style={{ pointerEvents: 'none' }} /> </div> <div className={styles.galleryCardContent}> <h3 className={styles.galleryCardTitle}>{site.title}</h3> <p className={styles.galleryCardDescription}>{site.description}</p> </div> </div> ))} </div> </section>
    </div>
  );
}