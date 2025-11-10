"use client";
import React, { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { Skeleton } from "@/components/ui/skeleton";
import PresentationMode from "../../components/PresentationMode";
import SidePanel from "./SidePanel";
import SlideContent from "./SlideContent";
import Header from "./Header";
import { Button } from "@/components/ui/button";
import { usePathname } from "next/navigation";
import { trackEvent, MixpanelEvent } from "@/utils/mixpanel";
import { AlertCircle, ExternalLink, Loader2 } from "lucide-react";
import Help from "./Help";
import {
  usePresentationStreaming,
  usePresentationData,
  usePresentationNavigation,
  useAutoSave,
} from "../hooks";
import { PresentationPageProps } from "../types";
import LoadingState from "./LoadingState";
import { useLayout } from "../../context/LayoutContext";
import { useFontLoader } from "../../hooks/useFontLoader";
import { usePresentationUndoRedo } from "../hooks/PresentationUndoRedo";

const formatDebugValue = (value: unknown): string => {
  // if (value === undefined || value === null) {
  //   return "—";
  // }

  // if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
  //   return String(value);
  // }

  // try {
  //   const serialized = JSON.stringify(value);
  //   return serialized.length > 120 ? `${serialized.slice(0, 117)}...` : serialized;
  // } catch {
  //   return "[unserializable]";
  // }
  return JSON.stringify(value);
};
const PresentationPage: React.FC<PresentationPageProps> = ({
  presentation_id,
}) => {
  const { t } = useTranslation("presentation");
  const pathname = usePathname();
  // State management
  const [loading, setLoading] = useState(true);
  const [selectedSlide, setSelectedSlide] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [error, setError] = useState(false);
  const [isMobilePanelOpen, setIsMobilePanelOpen] = useState(false);
  const [isResourcesPanelOpen, setIsResourcesPanelOpen] = useState(false);
  const [isMarkersPanelOpen, setIsMarkersPanelOpen] = useState(false);
  const {getCustomTemplateFonts} = useLayout();
 
  const { presentationData, isStreaming } = useSelector(
    (state: RootState) => {
      console.log("useSelector called, presentationData:", state.presentationGeneration.presentationData);
      console.log("useSelector webSearchResources:", state.presentationGeneration.presentationData?.webSearchResources);
      console.log("useSelector reference_markers:", state.presentationGeneration.presentationData?.reference_markers);
      return state.presentationGeneration;
    }
  );

  // Auto-save functionality
  const { isSaving } = useAutoSave({
    debounceMs: 2000,
    enabled: !!presentationData && !isStreaming,
  });

  // Custom hooks
  const { fetchUserSlides } = usePresentationData(
    presentation_id,
    setLoading,
    setError
  );

  const {
    isPresentMode,
    stream,
    handleSlideClick,
    toggleFullscreen,
    handlePresentExit,
    handleSlideChange,
  } = usePresentationNavigation(
    presentation_id,
    selectedSlide,
    setSelectedSlide,
    setIsFullscreen
  );

  // Initialize streaming
  usePresentationStreaming(
    presentation_id,
    stream,
    setLoading,
    setError,
    fetchUserSlides
  );

  usePresentationUndoRedo();

  const onSlideChange = (newSlide: number) => {
    handleSlideChange(newSlide, presentationData);
  };

  const webSearchResources = useMemo(() => {
    const rawResources =
      presentationData?.webSearchResources ??
      null;

    console.log("PresentationPage - rawResources:", rawResources);
    console.log("PresentationPage - presentationData:", presentationData);

    if (!rawResources) {
      console.log("PresentationPage - no rawResources found, returning empty object");
      return {} as any;
    }

    if (Array.isArray(rawResources)) {
      return rawResources.filter(Boolean);
    }

    if (typeof rawResources === "string") {
      try {
        const parsed = JSON.parse(rawResources);
        if (Array.isArray(parsed)) {
          return parsed.filter(Boolean);
        }
        if (parsed && typeof parsed === "object") {
          if (Array.isArray(parsed.items)) {
            return parsed.items.filter(Boolean);
          }
          // Return the object directly instead of wrapping in array
          return parsed;
        }
      } catch (error) {
        console.warn("Failed to parse webSearchResources string", error);
        return {} as any;
      }
    }

    if (typeof rawResources === "object") {
      if (Array.isArray((rawResources as any).items)) {
        return (rawResources as any).items.filter(Boolean);
      }
      // Return the object directly instead of wrapping in array
      return rawResources;
    }

    return {} as any;
  }, [presentationData]);


  const referenceMarkers = useMemo(() => {
    const rawMarkers = presentationData?.reference_markers ??  null;

    console.log("PresentationPage - rawMarkers:", rawMarkers);

    if (!rawMarkers) {
      console.log("PresentationPage - no rawMarkers found, returning empty array");
      return [] as any[];
    }

    if (Array.isArray(rawMarkers)) {
      return rawMarkers.filter(Boolean);
    }

    if (typeof rawMarkers === "string") {
      try {
        const parsed = JSON.parse(rawMarkers);
        if (Array.isArray(parsed)) {
          return parsed.filter(Boolean);
        }
        if (parsed && typeof parsed === "object") {
          if (Array.isArray(parsed.items)) {
            return parsed.items.filter(Boolean);
          }
          return [parsed];
        }
      } catch (error) {
        console.warn("Failed to parse reference_markers string", error);
        return [] as any[];
      }
    }

    if (typeof rawMarkers === "object") {
      if (Array.isArray((rawMarkers as any).items)) {
        return (rawMarkers as any).items.filter(Boolean);
      }
      return [rawMarkers];
    }

    return [] as any[];
  }, [presentationData]);


  useEffect(() => {
    if(!loading && !isStreaming && presentationData?.slides && presentationData?.slides.length > 0){  
      const templateId = presentationData?.slides[0].layout.split(":")[0].split("custom-")[1];
      const fonts = getCustomTemplateFonts(templateId);
    
      useFontLoader(fonts || []);
    }
  }, [presentationData,loading,isStreaming]);
  // Presentation Mode View
  if (isPresentMode) {
    return (
      <PresentationMode
        slides={presentationData?.slides!}
        currentSlide={selectedSlide}
        isFullscreen={isFullscreen}
        onFullscreenToggle={toggleFullscreen}
        onExit={handlePresentExit}
        onSlideChange={onSlideChange}
      />
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-100 px-2 md:px-4">
        <div
          className="bg-white border border-red-300 text-red-700 px-6 py-8 rounded-lg shadow-lg flex flex-col items-center"
          role="alert"
        >
          <AlertCircle className="w-16 h-16 mb-4 text-red-500" />
          <h2 className="text-xl font-semibold mb-2">{t("something_went_wrong")}</h2>
          <p className="text-center mb-4">
            {t("we_couldnt_load_your_presentation_please_try_again")}
          </p>
          <Button className="bg-indigo-600 text-white hover:bg-indigo-500" onClick={() => { trackEvent(MixpanelEvent.PresentationPage_Refresh_Page_Button_Clicked, { pathname }); window.location.reload(); }}>{t("refresh_page")}</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex overflow-hidden flex-col">

      {/* Debug Panel - Show in all environments */}
      {false && (
        <div className="fixed top-20 right-4 z-50 bg-black bg-opacity-80 text-white p-4 rounded-lg max-w-sm max-h-96 overflow-auto">
          <h3 className="font-bold mb-2">Debug Info</h3>
          <div className="text-xs space-y-1">            
            <div><strong>reference_markers:</strong> {formatDebugValue(presentationData?.reference_markers)}</div>
            <div><strong>webSearchResources:</strong> {formatDebugValue(presentationData?.webSearchResources)}</div>
          </div>
        </div>
      )}
     

      <Header presentation_id={presentation_id} currentSlide={selectedSlide} />
      <Help />

     

      <div
        style={{
          background: "#c8c7c9",
        }}
        className="flex flex-1 relative pt-6"
      >
        <SidePanel
          selectedSlide={selectedSlide}
          onSlideClick={handleSlideClick}
          loading={loading}
          isMobilePanelOpen={isMobilePanelOpen}
          setIsMobilePanelOpen={setIsMobilePanelOpen}
        />
        
        <div className="flex-1 h-[calc(100vh-100px)] overflow-y-auto">
          <div
            id="presentation-slides-wrapper"
            className="mx-auto flex flex-col items-center overflow-hidden justify-center p-2 md:p-6 pt-0"
          >
            {!presentationData ||
            loading ||
            !presentationData?.slides ||
            presentationData?.slides.length === 0 ? (
              <div className="relative w-full h-[calc(100vh-120px)] mx-auto">
                <div className="">
                  {Array.from({ length: 2 }).map((_, index) => (
                    <Skeleton
                      key={index}
                      className="aspect-video bg-gray-400 my-4 w-full mx-auto max-w-[1280px]"
                    />
                  ))}
                </div>
                {stream && <LoadingState />}
              </div>
            ) : (
              <>
                {presentationData &&
                  presentationData.slides &&
                  presentationData.slides.length > 0 &&
                  presentationData.slides.map((slide: any, index: number) => (
                    <SlideContent
                      key={`${slide.type}-${index}-${slide.index}`}
                      slide={slide}
                      index={index}
                      presentationId={presentation_id}
                    referenceMarkers={referenceMarkers}
                    webSearchResources={webSearchResources}
                    />
                  ))}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PresentationPage;
