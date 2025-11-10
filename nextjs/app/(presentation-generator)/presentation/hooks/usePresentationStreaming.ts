'use client'
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useDispatch, useSelector } from "react-redux";
import {
  clearPresentationData,
  setPresentationData,
  setStreaming
} from "@/store/slices/presentationGeneration";
import { jsonrepair } from "jsonrepair";
import { toast } from "sonner";
import { MixpanelEvent, trackEvent } from "@/utils/mixpanel";
import { RootState } from "@/store/store";
import { PresentationData } from "@/store/slices/presentationGeneration";
import { store } from "@/store/store";

export const usePresentationStreaming = (
  presentationId: string,
  stream: string | null,
  setLoading: (loading: boolean) => void,
  setError: (error: boolean) => void,
  fetchUserSlides: () => void
) => {
  const { t } = useTranslation("presentation");
  const dispatch = useDispatch();
  const previousSlidesLength = useRef(0);
  const presentationDataRef = useRef<PresentationData | null>(null);

  const presentationData = useSelector(
    (state: RootState) => state.presentationGeneration.presentationData
  );

  useEffect(() => {
    presentationDataRef.current = presentationData;
  }, [presentationData]);

  useEffect(() => {
    let eventSource: EventSource;
    let accumulatedChunks = "";

    const initializeStream = async () => {
      dispatch(setStreaming(true));
      dispatch(clearPresentationData());

      trackEvent(MixpanelEvent.Presentation_Stream_API_Call);

      eventSource = new EventSource(
        `/api/v1/ppt/presentation/stream/${presentationId}`
      );

      eventSource.addEventListener("response", (event) => {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case "chunk": {
            const currentData = presentationDataRef.current || ({} as PresentationData);
            accumulatedChunks += data.chunk;
            try {
              const repairedJson = jsonrepair(accumulatedChunks);
              const partialData = JSON.parse(repairedJson);

              if (partialData.slides) {
                if (
                  partialData.slides.length !== previousSlidesLength.current &&
                  partialData.slides.length > 0
                ) {
                  const mergedData = {
                    ...(currentData as any),
                    ...partialData,
                    slides: partialData.slides,
                    // Preserve webSearchResources if it exists in currentData, otherwise use from partialData
                    webSearchResources:
                      (currentData as any).webSearchResources ??
                      (partialData as any).webSearchResources,
                    reference_markers:
                      (currentData as any).reference_markers ??
                      (partialData as any).reference_markers,
                  } as PresentationData;
                  dispatch(
                    setPresentationData(mergedData)
                  );
                  previousSlidesLength.current = partialData.slides.length;
                  setLoading(false);
                }
              }
            } catch (error) {
              // JSON isn't complete yet, continue accumulating
            }
            break;
          }

            case "webSearchResources":
              console.log("Received webSearchResources event:", data);
              const currentDataWS = presentationDataRef.current || ({} as PresentationData);
              const resources = data.webSearchResources;
              console.log("Current presentationData before setting:", currentDataWS);
              console.log("Setting webSearchResources to Redux store:", resources);

              // 总是合并现有数据，确保不会覆盖其他字段
              const newData = {
                ...(currentDataWS as any),
                webSearchResources: resources,
                reference_markers: data.reference_markers,
              } as PresentationData;

              console.log("New data being dispatched (merged):", newData);
              dispatch(setPresentationData(newData));
              break;

              case "reference_marker":  // Also handle singular form
              if (data.reference_markers || data.reference_marker) {
                const markers = data.reference_markers || data.reference_marker;
                const currentData = presentationDataRef.current || ({} as PresentationData);
                console.log("Received reference_markers event:", markers);
                console.log("Current presentationData before setting reference_markers:", currentData);
                console.log("Setting reference_markers to Redux store:", markers);

                const newData = {
                  ...(currentData as any),
                  reference_markers: markers,
                } as PresentationData;

                console.log("New data being dispatched with reference_markers (merged):", newData);
                console.log("New reference_markers:", newData.reference_markers);

                dispatch(setPresentationData(newData));
              }
              break;
          case "complete": {
            try {
              console.log("Received complete event with presentation data:", data.presentation);
              console.log("Current presentationDataRef.current:", presentationDataRef.current);
              console.log("data.presentation.webSearchResources:", data.presentation?.webSearchResources);
              console.log("presentationDataRef.current.webSearchResources:", presentationDataRef.current?.webSearchResources);
              console.log("data.presentation.reference_markers:", data.presentation?.reference_markers);
              console.log("presentationDataRef.current.reference_markers:", presentationDataRef.current?.reference_markers);

              const finalPresentation = {
                ...data.presentation,
                // 优先使用服务端数据（如果存在且不为空），否则使用当前状态
                webSearchResources:
                  (data.presentation?.webSearchResources !== undefined && data.presentation?.webSearchResources !== null)
                    ? data.presentation.webSearchResources              
                    : presentationDataRef.current?.webSearchResources,
            
                reference_markers:
                  (data.presentation?.reference_markers !== undefined && data.presentation?.reference_markers !== null)
                    ? data.presentation.reference_markers          
                    : presentationDataRef.current?.reference_markers,
              } as PresentationData;

              console.log("Final presentation data being dispatched:", finalPresentation);
              console.log("Final webSearchResources:", finalPresentation.webSearchResources);
              console.log("Final reference_markers:", finalPresentation.reference_markers);

              dispatch(setPresentationData(finalPresentation));    
              dispatch(setStreaming(false));
              setLoading(false);
              eventSource.close();

              // Remove stream parameter from URL
              const newUrl = new URL(window.location.href);
              newUrl.searchParams.delete("stream");
              window.history.replaceState({}, "", newUrl.toString());
            } catch (error) {
              eventSource.close();
              console.error("Error parsing accumulated chunks:", error);
            }
            accumulatedChunks = "";
            break;        
          }

          case "closing":
            console.log("Received closing event with presentation data:", data.presentation);
            console.log("Current presentationDataRef.current:", presentationDataRef.current);

            // 合并数据，确保不丢失webSearchResources
            const closingData = {
              ...data.presentation,
              // 优先使用服务端数据（如果存在且不为空），否则使用当前状态
              webSearchResources:
                (data.presentation?.webSearchResources !== undefined && data.presentation?.webSearchResources !== null)
                  ? data.presentation.webSearchResources              
                  : presentationDataRef.current?.webSearchResources ,              
              reference_markers:
                (data.presentation?.reference_markers !== undefined && data.presentation?.reference_markers !== null)
                  ? data.presentation.reference_markers              
                  : presentationDataRef.current?.reference_markers,
            } as PresentationData;

            console.log("Closing data being dispatched:", closingData);
            console.log("Closing webSearchResources:", closingData.webSearchResources);
            console.log("Closing reference_markers:", closingData.reference_markers);

            dispatch(setPresentationData(closingData));
            setLoading(false);
            dispatch(setStreaming(false));
            eventSource.close();

            // Remove stream parameter from URL
            const newUrl = new URL(window.location.href);
            newUrl.searchParams.delete("stream");
            window.history.replaceState({}, "", newUrl.toString());
            break;
          case "error":
            eventSource.close();
            toast.error(t("error_in_outline_streaming"), {
              description:
                data.detail ||
                t("failed_to_connect_to_server_please_try_again"),
            });
            setLoading(false);
            dispatch(setStreaming(false));
            setError(true);
            break;
        }
      });

      eventSource.onerror = (error) => {
        console.error("EventSource failed:", error);
        setLoading(false);
        dispatch(setStreaming(false));
        setError(true);
        eventSource.close();
      };
    };

    if (stream) {
      initializeStream();
    } else {
      // 只有当 Redux 中没有数据时才获取数据，避免覆盖流式生成的数据
      const currentData = store.getState().presentationGeneration.presentationData;
      if (!currentData || !currentData.slides || currentData.slides.length === 0) {
        console.log("No existing data found, fetching user slides");
        fetchUserSlides();
      } else {
        console.log("Existing data found, skipping fetchUserSlides to preserve webSearchResources");
        setLoading(false);
      }
    }

    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [presentationId, stream, dispatch, setLoading, setError, fetchUserSlides]);
};
