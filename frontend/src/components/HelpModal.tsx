import { useState } from "react";
import Step1 from "../../images/Step_1.png";
import Step2 from "../../images/Step_2.png";
import Step3 from "../../images/Step_3.png";

const slides = [Step1, Step2, Step3];

interface HelpModalProps {
  onClose: () => void;
}

export function HelpModal({ onClose }: HelpModalProps) {
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-card help-modal" role="dialog" aria-modal="true" aria-labelledby="help-title">
        <div className="modal-header">
          <div>
            <h2 id="help-title">How to use Price Claw</h2>
          </div>
          <button className="button-secondary" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="slideshow-container">
          <img src={slides[currentSlideIndex]} alt={`Step ${currentSlideIndex + 1}`} className="slideshow-image" />
        </div>

        <div className="slideshow-controls">
          <button
            className="button-secondary"
            onClick={() => setCurrentSlideIndex(Math.max(0, currentSlideIndex - 1))}
            disabled={currentSlideIndex === 0}
          >
            Previous
          </button>
          <span>
            Step {currentSlideIndex + 1} of {slides.length}
          </span>
          <button
            className="button-primary"
            onClick={() => setCurrentSlideIndex(Math.min(slides.length - 1, currentSlideIndex + 1))}
            disabled={currentSlideIndex === slides.length - 1}
          >
            Next
          </button>
        </div>
      </section>
    </div>
  );
}
