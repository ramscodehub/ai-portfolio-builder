"use client";

import { useState, FormEvent, useEffect } from "react";
import styles from "./DarkHomePage.module.css"; 

// --- Icons (keep as they were) ---
const ArrowUpIcon = () => ( <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" style={{width: '18px', height: '18px'}}> <path fillRule="evenodd" d="M10 17a.75.75 0 0 1-.75-.75V5.56l-2.47 2.47a.75.75 0 0 1-1.06-1.06l3.75-3.75a.75.75 0 0 1 1.06 0l3.75 3.75a.75.75 0 1 1-1.06 1.06L10.75 5.56v10.69A.75.75 0 0 1 10 17Z" clipRule="evenodd" /> </svg> );
const AiIconPlaceholder = () => ( <div style={{ width: '28px', height: '28px', background: 'linear-gradient(135deg, #BB86FC, #6200EE)', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '14px' }}>AI</div> );

// --- Interfaces ---
interface GalleryItem {
  id: string;
  viewLink: string; 
  category: string;
  title: string; 
  description?: string;
}

interface CloneApiResponse { 
    message: string;
    file_path: string; 
    view_link?: string; 
}

// Static Gallery Data (files must exist in frontend/public/generated_html_clones/)
const allGalleryItems: GalleryItem[] = [
  { id: "ola", viewLink: "/generated_html_clones/clone_www_olacabs_com_20250605_183343.html", category: "Landing Pages", title: "Ola Cabs", description: "Ride Hailing Service" },
  { id: "lyft", viewLink: "/generated_html_clones/clone_www_lyft_com_20250606_162527.html", category: "Landing Pages", title: "Lyft.com", description: "Rideshare Service" }, // Corrected title
  { id: "fitness", viewLink: "/generated_html_clones/clone_fittrack-landing-page-smoky_vercel_app_20250606_151340.html", category: "Landing Pages", title: "FitTrack", description: "Fitness Platform"}, // Added leading slash
  { id: "wix", viewLink: "/generated_html_clones/clone_www_wix_com_20250605_190834.html", category: "Landing Pages", title: "Wix.com", description: "Website Builder" },
  { id: "wordpress", viewLink: "/generated_html_clones/clone_wordpress_com_20250605_222253.html", category: "Landing Pages", title: "WordPress.com", description: "Blogging Platform" },
  { id: "simplegreet", viewLink: "/generated_html_clones/clone_simple-greetings-1748253405653_vercel_app_20250605_193006.html", category: "Landing Pages", title: "Simple Greetings", description: "Portfolio Example" },
  { id: "uber", viewLink: "/generated_html_clones/clone_www_uber_com_20250605_175014.html", category: "Landing Pages", title: "Uber.com", description: "Ride & Delivery" },
];

export default function HomePage() {
  const [url, setUrl] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [showUnoLink, setShowUnoLink] = useState<boolean>(false);
  
  const [filteredGalleryItems, setFilteredGalleryItems] = useState<GalleryItem[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("Landing Pages"); 

  const categories = ["Landing Pages", "All"];
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  useEffect(() => {
    if (activeCategory === "All") {
      setFilteredGalleryItems(allGalleryItems);
    } else {
      setFilteredGalleryItems(allGalleryItems.filter(item => item.category === activeCategory));
    }
  }, [activeCategory]); 

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!url) { setError("Please enter a website URL."); return; }
    
    setIsLoading(true); 
    setError(null); 
    setStatusMessage("Initiating cloning process... This may take 4-5 minutes.");
    setShowUnoLink(true);

    try {
        const response = await fetch(`${BACKEND_URL}/clone-website-and-save`, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }),
        });
        
        if (!response.ok) {
            let errorDetail = `Error: ${response.status} ${response.statusText}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; }
            catch (e) { /* Ignore if error response is not JSON */ }
            throw new Error(errorDetail);
        }
        const data: CloneApiResponse = await response.json();
        
        setShowUnoLink(false);
        setStatusMessage(data.message || "Cloning process completed!");

        if (data.view_link) {
            // Open the newly generated clone in a new tab
            window.open(data.view_link, '_blank', 'noopener,noreferrer');
        } else {
            setError("Cloned successfully by backend, but no viewable link was returned.");
        }
    } catch (err: any) {
        setError(err.message || "Failed to clone website.");
        setStatusMessage("Cloning process failed.");
        setShowUnoLink(false);
        console.error("Cloning Error:", err);
    } finally {
        setIsLoading(false);
    }
  };
  
  // Function to handle click on a gallery card - opens its viewLink in a new tab
  const handleGalleryCardClick = (viewLink: string) => {
    window.open(viewLink, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className={styles.mainContainer}>
      <header className={styles.header}>
        <div className={styles.logoContainer}> <AiIconPlaceholder /> </div>
      </header>

      <section className={styles.heroSection}>
        <h1 className={styles.heroHeadline}>Make a website in seconds</h1>
        <p className={styles.heroSubHeadline}>Start, iterate, and launch your website all in one place</p>
        <form onSubmit={handleSubmit} className={styles.inputArea}>
          <input type="text" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Enter website URL to clone" className={styles.urlInput} required disabled={isLoading} />
          <button type="submit" className={styles.submitButton} disabled={isLoading} aria-label="Clone website"> <ArrowUpIcon /> </button>
        </form>
      </section>

      {(isLoading || statusMessage || error) && (
        <div className={styles.statusMessageContainer}>
          {isLoading && statusMessage && <p className={styles.statusMessage}>{statusMessage}</p>}
          {isLoading && showUnoLink && (
            <p className={styles.unoLinkMessage}>
              "Our AI is hard at work cloning your site (it takes about 4-5 mins)! In the meantime, you can check out another project of mine: a fun <a href="https://unoapp-qpfg65xn6a-ue.a.run.app/" target="_blank" rel="noopener noreferrer" className={styles.unoLink}>UNO game!</a>"
            </p>
          )}
          {!isLoading && statusMessage && !error && <p className={styles.statusMessage}>{statusMessage}</p>}
          {error && <p className={styles.errorMessage}>{error}</p>}
        </div>
      )}
      
      {/* Main preview iframe section is removed as all previews open in new tabs */}

      <section className={styles.gallerySection}>
        <h2 className={styles.galleryMainTitle}>Websites made with this service</h2>
        <p className={styles.gallerySubTitle}>Click on any card to visit the live site</p>
        <div className={styles.categoryButtons}>
          {categories.map((category) => (
            <button key={category} className={`${styles.categoryButton} ${activeCategory === category ? styles.active : ''}`} onClick={() => setActiveCategory(category)}> {category} </button>
          ))}
        </div>
        {filteredGalleryItems.length > 0 ? (
          <div className={styles.galleryGrid}>
            {filteredGalleryItems.map((site) => (
              // Card itself is clickable
              <div 
                key={site.id} 
                className={styles.galleryCard} // Apply card styles
                onClick={() => handleGalleryCardClick(site.viewLink)} // Opens in new tab
                style={{ cursor: 'pointer' }} // Indicate it's clickable
              >
                <div className={styles.galleryCardPreviewContainer}>
                  <iframe 
                    src={site.viewLink} 
                    className={styles.galleryCardPreview} 
                    title={`Preview of ${site.title}`} 
                    sandbox="allow-scripts allow-same-origin" // For inline preview
                    scrolling="no" 
                    style={{ pointerEvents: 'none' }} // Keeps click on the parent div
                  />
                </div>
                <div className={styles.galleryCardContent}>
                  <h3 className={styles.galleryCardTitle}>{site.title}</h3>
                  <p className={styles.galleryCardDescription}>{site.description}</p>
                </div>
              </div>
            ))}
          </div>
        ) : ( 
          <p style={{textAlign: 'center', color: 'var(--secondary-text-color)'}}>
            No websites to display for this category.
          </p> 
        )}
      </section>
    </div>
  );
}