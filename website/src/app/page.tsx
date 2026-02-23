import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Features from "@/components/Features";
import PrivacySection from "@/components/PrivacySection";
import HowItWorks from "@/components/HowItWorks";
import QuickSetup from "@/components/QuickSetup";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <Features />
        <PrivacySection />
        <HowItWorks />
        <QuickSetup />
      </main>
      <Footer />
    </>
  );
}
