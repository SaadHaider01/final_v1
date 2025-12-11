import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Problem from './pages/Problem';
import Architecture from './pages/Architecture';
import Playground from './pages/Playground';
import Results from './pages/Results';
import References from './pages/References';
import About from './pages/About';

function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/problem" element={<Problem />} />
      <Route path="/architecture" element={<Architecture />} />
      <Route path="/playground" element={<Playground />} />
      <Route path="/results" element={<Results />} />
      <Route path="/references" element={<References />} />
      <Route path="/about" element={<About />} />
    </Routes>
  );
}

export default AppRouter;
