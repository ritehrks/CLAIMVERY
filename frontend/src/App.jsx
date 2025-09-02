    // frontend/src/App.jsx

    import React, { useState } from 'react';
    import axios from 'axios';

    // Form Component
    const ClaimForm = ({ setResults, setLoading, setError }) => {
        const handleSubmit = async (e) => {
            e.preventDefault();
            setLoading(true);
            setError(null);
            setResults(null);

            const formData = new FormData(e.target);
            
            try {
                const response = await axios.post('http://localhost:5001/api/verify', formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data',
                    },
                });
                setResults(response.data);
            } catch (err) {
                const errorMessage = err.response?.data?.details || err.response?.data?.error || 'An unexpected error occurred.';
                setError(errorMessage);
            } finally {
                setLoading(false);
            }
        };

        return (
            <div className="bg-white p-6 md:p-8 rounded-xl shadow-lg border border-gray-200">
                <form onSubmit={handleSubmit}>
                    <div className="mb-6">
                        <label htmlFor="claim" className="block text-sm font-medium text-gray-700 mb-2">Claim / Question</label>
                        <textarea id="claim" name="original_claim" rows="2" className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" placeholder="Type or paste the claim here..." required></textarea>
                    </div>

                    <div className="mb-6">
                        <label htmlFor="source_identifier" className="block text-sm font-medium text-gray-700 mb-2">Source URL (Optional)</label>
                        <input type="text" id="source_identifier" name="source_identifier" className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" placeholder="e.g., https://www.bbc.com/news/..." />
                    </div>

                    <div className="mb-6">
                        <label htmlFor="claimImage" className="block text-sm font-medium text-gray-700 mb-2">Upload Screenshot (Optional)</label>
                        <input type="file" id="claimImage" name="claimImage" accept="image/*" className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
                    </div>
                    
                    <button type="submit" className="w-full bg-blue-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 transition-all duration-300 shadow-md">
                        Investigate
                    </button>
                </form>
            </div>
        );
    };

    // Results Component
    const ResultsDisplay = ({ results, loading, error }) => {
        if (loading) {
            return (
                <div className="bg-white mt-8 rounded-xl shadow-lg p-8 text-center">
                    <div className="flex flex-col items-center justify-center">
                        <div className="loader mb-4"></div>
                        <p className="text-lg font-semibold text-gray-800">Agent is Investigating...</p>
                        <p className="text-sm text-gray-500">This may take a moment.</p>
                    </div>
                </div>
            );
        }
        if (error) {
            return (
                <div className="bg-white mt-8 rounded-xl shadow-lg p-8">
                    <h3 className="text-lg font-bold text-red-600">An Error Occurred</h3>
                    <pre className="bg-red-50 text-red-800 p-4 rounded-lg mt-2 whitespace-pre-wrap break-all text-xs">{error}</pre>
                </div>
            );
        }
        if (!results) return null;

        return (
            <div className="bg-white mt-8 rounded-xl shadow-lg p-6 md:p-8">
                <div className="mb-6">
                    <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Final Verdict</h2>
                    <p className="text-3xl font-bold text-gray-900">{results.final_verdict || 'N/A'}</p>
                </div>
                <div className="mb-6">
                    <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Verdict Explanation</h2>
                    <p className="text-gray-700 leading-relaxed bg-gray-50 p-4 rounded-lg border">{results.verdict_explanation}</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                    <div className="bg-gray-50 p-4 rounded-lg border">
                        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-1">Claim Analysis</h3>
                        <p className="text-gray-700 text-sm">{results.claim_analysis_summary}</p>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-lg border">
                        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-1">Source Analysis</h3>
                        <p className="text-gray-700 text-sm">{results.source_analysis_summary}</p>
                    </div>
                </div>
                <div>
                    <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Key Sources Found</h2>
                    <ul className="space-y-3">
                        {results.detailed_sources?.length > 0 ? results.detailed_sources.map((source, index) => (
                            <li key={index} className="bg-white p-3 rounded-lg border border-gray-200 hover:border-blue-500 transition">
                                <a href={source.url} target="_blank" rel="noopener noreferrer" className="font-medium text-blue-700 hover:underline">{source.title}</a>
                                <p className="text-sm text-gray-600 mt-1 italic">"{source.relevance_summary}"</p>
                            </li>
                        )) : <li className="text-gray-500">No key sources were cited in the final report.</li>}
                    </ul>
                </div>
            </div>
        );
    };

    // Main App Component
    function App() {
        const [results, setResults] = useState(null);
        const [loading, setLoading] = useState(false);
        const [error, setError] = useState(null);

        return (
            <div className="min-h-screen p-4">
                <div className="w-full max-w-3xl mx-auto">
                    <header className="text-center my-8">
                        <h1 className="text-4xl md:text-5xl font-extrabold text-gray-900 tracking-tight">Claim Verification Agent</h1>
                        <p className="mt-3 text-lg text-gray-600">Investigate any claim, question, or screenshot with an advanced AI research agent.</p>
                    </header>
                    <main>
                        <ClaimForm setResults={setResults} setLoading={setLoading} setError={setError} />
                        <ResultsDisplay results={results} loading={loading} error={error} />
                    </main>
                </div>
            </div>
        );
    }

    export default App;
    