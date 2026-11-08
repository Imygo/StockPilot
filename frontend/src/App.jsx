import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import StockDetail from './pages/StockDetail';
import UserRegister from './pages/UserRegister';
import RequireSession from './components/RequireSession';

function App() {
  return (
    <BrowserRouter>
        <Routes>
            <Route path="/register" element={<UserRegister />} />

            <Route element={<RequireSession />}>
                <Route path="/" element={<Home />} />
                <Route path="/stock/:code" element={<StockDetail />} />
            </Route>
        </Routes>
    </BrowserRouter>
  );
}

export default App;