"use client";

import { useState, FormEvent } from "react";
import Image from 'next/image'; // <-- IMPORTANT: Import the Next.js Image component
import styles from "./DarkHomePage.module.css"; 

// --- Icons (as before) ---
const AiIconPlaceholder = () => ( <div style={{ width: '28px', height: '28px', background: 'linear-gradient(135deg, #BB86FC, #6200EE)', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '14px' }}>AI</div> );

// --- UPDATED Interface ---
interface GalleryItem { 
  id: string;
  viewLink: string; 
  previewImageUrl: string; // <-- NEW: Path to the screenshot in /public
  title: string; 
  description?: string;
}

interface CloneApiResponse { message: string; file_path: string; view_link?: string; }

// --- UPDATED Static Gallery Data ---
const galleryItems: GalleryItem[] = [
  { 
    id: "p1", 
    viewLink: "https://d12dmeynqgk1fi.cloudfront.net/portfolios/prudhvi_ram_mannuru_portfolio_20250705_113015.html",
    previewImageUrl: "/gallery_previews/p1.png",
    title: "Portfolio", 
    description: "Style: Modern & Minimal" 
  },
  { 
    id: "p2", 
    viewLink: "https://d12dmeynqgk1fi.cloudfront.net/portfolios/prudhvi_ram_mannuru_portfolio_20250628_194319.html",
    previewImageUrl: "/gallery_previews/p2.png",
    title: "Portfolio", 
    description: "Style: Creative & Playful" 
  },
  { 
    id: "p3", 
    viewLink: "https://d12dmeynqgk1fi.cloudfront.net/portfolios/prudhvi_ram_mannuru_portfolio_20250705_165357.html",
    previewImageUrl: "/gallery_previews/p3.png",
    title: "Portfolio", 
    description: "Style: Tech Blog Inspired" 
  },
  { 
    id: "p4", 
    viewLink: "https://d12dmeynqgk1fi.cloudfront.net/portfolios/prudhvi_ram_mannuru_portfolio_20250701_205318.html",
    previewImageUrl: "/gallery_previews/p4.png",
    title: "Portfolio", 
    description: "Style: Professional SaaS" 
  },
];

export default function HomePage() {
  const [referenceUrl, setReferenceUrl] = useState<string>("");
  const [resumeText, setResumeText] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [showUnoLink, setShowUnoLink] = useState<boolean>(false);
  
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  // The category filtering logic is no longer needed

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    // This function remains unchanged
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
  
  return (
    <div className={styles.mainContainer}>
      {/* --- Header and Hero Section (no changes) --- */}
      <header className={styles.header}>
        <div className={styles.logoContainer}> <AiIconPlaceholder /> </div>
      </header>
      <section className={styles.heroSection}>
        <h1 className={styles.heroHeadline}>Build your portfolio in seconds</h1>
        <p className={styles.heroSubHeadline}>Provide a reference portfolio for style, and your resume for content.</p>
        <form onSubmit={handleSubmit} className={styles.inputForm}>
          <div className={styles.inputCard}>
            <label htmlFor="referenceUrl" className={styles.inputLabel}>Reference Portfolio URL</label>
            <input id="referenceUrl" type="url" value={referenceUrl} onChange={(e) => setReferenceUrl(e.target.value)} placeholder="https://www.example-portfolio.com" className={styles.urlInput} required disabled={isLoading} />
          </div>
          <div className={styles.inputCard}>
            <label htmlFor="resumeText" className={styles.inputLabel}>Your Resume / Profile Info</label>
            <textarea id="resumeText" value={resumeText} onChange={(e) => setResumeText(e.target.value)} placeholder="Paste your full resume or professional bio here..." className={styles.resumeTextarea} required disabled={isLoading} />
          </div>
          <div className={styles.submitButtonContainer}>
            <button type="submit" className={styles.submitButton} disabled={isLoading} aria-label="Build Portfolio">
              <span>Build My Portfolio</span>
            </button>
          </div>
        </form>
      </section>
      {(isLoading || statusMessage || error) && ( <div className={styles.statusMessageContainer}> {isLoading && statusMessage && <p className={styles.statusMessage}>{statusMessage}</p>} {isLoading && showUnoLink && ( <p className={styles.unoLinkMessage}> While you wait, feel free to play a game of <a href="https://unoapp-qpfg65xn6a-ue.a.run.app/" target="_blank" rel="noopener noreferrer" className={styles.unoLink}>UNO that I built!</a> </p> )} {!isLoading && statusMessage && !error && <p className={styles.statusMessage}>{statusMessage}</p>} {error && <p className={styles.errorMessage}>{error}</p>} </div> )}
      
      {/* --- UPDATED GALLERY SECTION --- */}
      <section className={styles.gallerySection}>
        <h2 className={styles.galleryMainTitle}>Portfolios Generated with this Service</h2>
        <p className={styles.gallerySubTitle}>Click any card to visit the live site</p>
        
        <div className={styles.galleryGrid}>
          {galleryItems.map((site) => (
            <a 
              key={site.id} 
              href={site.viewLink} 
              target="_blank" 
              rel="noopener noreferrer" 
              className={styles.galleryCardLinkWrapper}
            >
              <div className={styles.galleryCard}>
                <div className={styles.galleryCardPreviewContainer}>
                  {/* The iframe is now replaced with the Next.js Image component */}
                  <Image
                    src={site.previewImageUrl}
                    alt={`Screenshot preview for ${site.title}`}
                    fill // The 'fill' prop makes the image fill its parent container
                    className={styles.galleryCardPreviewImage}
                  />
                </div>
                <div className={styles.galleryCardContent}>
                  <h3 className={styles.galleryCardTitle}>{site.title}</h3>
                  <p className={styles.galleryCardDescription}>{site.description}</p>
                </div>
              </div>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}