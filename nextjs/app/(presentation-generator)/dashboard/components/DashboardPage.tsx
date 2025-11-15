"use client";

import React, { useState, useEffect } from "react";
import { useTranslation } from 'react-i18next';

import Wrapper from "@/components/Wrapper";
import { DashboardApi } from "@/app/(presentation-generator)/services/api/dashboard";
import { PresentationGrid } from "@/app/(presentation-generator)/dashboard/components/PresentationGrid";


import Header from "@/app/(presentation-generator)/dashboard/components/Header";

const DashboardPage: React.FC = () => {
  const { t } = useTranslation('dashboard');
  const [presentations, setPresentations] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const addReferenceMarker = (data: any) => {
    // 处理演示文稿数据的引用标记逻辑
    console.log('Adding reference markers to presentations:', data);
    // 如果需要特定的处理逻辑，可以在这里添加
  };
  
  useEffect(() => {
    const loadData = async () => {
      await fetchPresentations();
    };
    loadData();
  }, []);

  const fetchPresentations = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await DashboardApi.getPresentations();
      data.sort(
        (a: any, b: any) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );
      setPresentations(data);
      addReferenceMarker(data);
    } catch (err) {
      setError(null);
      setPresentations([]);
    } finally {
      setIsLoading(false);
    }
  };

  const removePresentation = (presentationId: string) => {
    setPresentations((prev: any) =>
      prev ? prev.filter((p: any) => p.id !== presentationId) : []
    );
  };

  return (
    <div className="min-h-screen bg-[#E9E8F8]">
      <Header />
      <Wrapper>
        <main className="container mx-auto py-4 md:py-8">
          <section>
            <h2 className="text-2xl font-roboto font-medium mb-6">
              {t('slidePresentation')}
            </h2>
            <PresentationGrid
              presentations={presentations}
              type="slide"
              isLoading={isLoading}
              error={error}
              onPresentationDeleted={removePresentation}
            />
          </section>
        </main>
      </Wrapper>
    </div>
  );
};

export default DashboardPage;
