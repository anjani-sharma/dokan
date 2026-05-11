export default function Footer() {
  return (
    <footer className="app-footer">
      <div className="footer-inner">
        <span className="footer-product">Product of</span>
        <img src="/ai-transformer.png" alt="AI Transformer" className="footer-logo" />
        <span className="footer-brand">AI Transformer</span>
        <span className="footer-sep">·</span>
        <span className="footer-copy">© {new Date().getFullYear()} DOKANE</span>
      </div>
    </footer>
  );
}
