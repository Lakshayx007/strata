import type { Findings } from './types';
import findingsData from './data/findings.json';
import { useTheme } from './useTheme';
import Nav from './components/Nav';
import Hero from './components/Hero';
import ShareOfVoice from './components/ShareOfVoice';
import WhyTeamsSwitch from './components/WhyTeamsSwitch';
import Voices from './components/Voices';
import ClouderaLens from './components/ClouderaLens';
import HowItWasBuilt from './components/HowItWasBuilt';
import Footer from './components/Footer';

const data = findingsData as Findings;

export default function App() {
  const { theme, toggle } = useTheme();

  return (
    <div className="min-h-screen flex flex-col">
      <Nav theme={theme} toggleTheme={toggle} />
      <main className="flex-1">
        <Hero data={data} />
        <ShareOfVoice data={data} />
        <WhyTeamsSwitch data={data} />
        <Voices data={data} />
        <ClouderaLens data={data} />
        <HowItWasBuilt data={data} />
      </main>
      <Footer data={data} />
    </div>
  );
}
