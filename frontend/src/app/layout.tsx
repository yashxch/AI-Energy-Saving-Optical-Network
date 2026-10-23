import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AI-Based Power Saving in Optical Networks | Nokia 1830 PSS Simulation',
  description: 'Intelligent Optical Transport Network power optimization using AI, LLM Reasoning, LSTM Traffic Forecasting, Isolation Forest Anomaly Detection, and Policy Validation.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  )
}
