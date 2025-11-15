import React, { useEffect, useState, useMemo } from 'react'
import {
	Loader2,
	PlusIcon,
	Trash2,
	WandSparkles,
	StickyNote,
	BookOpen,
} from 'lucide-react'
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from '@/components/ui/popover'
import { Textarea } from '@/components/ui/textarea'
import { SendHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import { PresentationGenerationApi } from '../../services/api/presentation-generation'
import ToolTip from '@/components/ToolTip'
import { RootState } from '@/store/store'
import { useDispatch, useSelector } from 'react-redux'
import { PresentationData } from '@/store/slices/presentationGeneration'
import {
	deletePresentationSlide,
	updateSlide,
} from '@/store/slices/presentationGeneration'
import { useTemplateLayouts } from '../../hooks/useTemplateLayouts'
import { usePathname } from 'next/navigation'
import { trackEvent, MixpanelEvent } from '@/utils/mixpanel'
import NewSlide from '../../components/NewSlide'
import { addToHistory } from '@/store/slices/undoRedoSlice'
import { useTranslation } from 'react-i18next'

interface SlideContentProps {
	slide: any
	index: number
	presentationId: string
	referenceMarkers: any[]
	webSearchResources: any
}

const SlideContent = ({ slide, index, presentationId, referenceMarkers, webSearchResources }: SlideContentProps) => {

	// Function to render reference markers with linked web search resources
	const renderReferenceMarkersWithResources = (index?: any,testSlide?: any, testMarkers?: any[], testResources?: any[] | any) => {
		const markers = testMarkers || referenceMarkers;
		const resources = testResources || webSearchResources;
		const slideIndex = testSlide ? testSlide.index : index;

		console.log("=== renderReferenceMarkersWithResources Debug ===");
		console.log("slide.index:", slideIndex);
		console.log("referenceMarkers:", markers);
		console.log("webSearchResources:", resources);

		if (!markers || !Array.isArray(markers)) {
			console.log("Data validation failed - markers not array");
			return <p className="text-xs text-red-500">Invalid data format</p>;
		}

		if (!resources) {
			console.log("Data validation failed - resources null/undefined");
			return <p className="text-xs text-red-500">Invalid data format</p>;
		}

		// Filter reference markers for current slide
		const slideMarkers = markers.filter((marker: any) =>
			marker && marker.slide_index === (slideIndex + 1)
		);

		// Function to filter out garbled text and unwanted characters
		const filterContent = (text: string) => {
			if (!text) return text;
			return text
				.replace(/[\x00-\x1F\x7F-\x9F]/g, '') // Remove control characters
				.replace(/[=\-—]{2,}/g, '') // Remove multiple equals signs or dashes
				.replace(/等+/g, '') // Remove "等" characters
				.replace(/[^\w\s\u4e00-\u9fff.,!?:;()[\]{}'"]+/g, '') // Keep only letters, numbers, Chinese characters, and common punctuation
				.replace(/\s+/g, ' ') // Normalize whitespace
				.trim();
		};

		// Function to get web resource by index
		const getWebResource = (resourceIndex: any) => {
			if (resourceIndex === null || resourceIndex === undefined) return null;

			let webResource = null;
			if (Array.isArray(resources)) {
				// Handle array format (original format)
				webResource = resources[resourceIndex] || null;
			} else if (typeof resources === 'object' && resources !== null) {
				// Handle object format with string keys (user's format)
				const resourceKey = resourceIndex.toString();
				webResource = resources[resourceKey] || null;

				// Also try with numeric key if string key doesn't work
				if (!webResource && typeof resourceIndex === 'number') {
					webResource = resources[resourceIndex] || null;
				}
			}
			return webResource;
		};

		console.log("Filtered slideMarkers for slide", slideIndex, ":", slideMarkers);

		if (slideMarkers.length === 0) {
			return <p className="text-xs text-gray-500">No reference markers for this slide (slide.index: {slideIndex})</p>;
		}

		// Filter out duplicate webResource.title only
		const seen = new Set();
		const uniqueMarkers = slideMarkers.filter((marker: any) => {
			const webResource = getWebResource(marker.reference_marker_index);
			const key = webResource?.title || '';
			if (seen.has(key)) {
				return false;
			}
			seen.add(key);
			return true;
		});

		console.log("Unique markers after filtering duplicates:", uniqueMarkers);

		return uniqueMarkers.map((marker: any, markerIndex: number) => {
			const resourceIndex = marker.reference_marker_index;
			const webResource = getWebResource(resourceIndex);

			console.log(`Marker ${markerIndex}:`, marker.content, "-> reference_marker_index:", marker.reference_marker_index, "-> extracted index:", resourceIndex);
			console.log(`Web resource for index ${resourceIndex} (type: ${typeof resourceIndex}):`, webResource);

			return (
				<div key={`marker-${markerIndex}`} className="border-b border-gray-100 pb-2 mb-2 last:border-b-0">
					<div className="text-sm">
						{webResource ? (
							<ToolTip
								content={webResource.content ? filterContent(webResource.content).match(/.{1,20}/g)?.slice(0, 3)?.join('\n') || filterContent(webResource.content) : 'Open link'}
								className="text-white bg-black bg-opacity-80 text-left px-2 whitespace-pre-line"
							>
								<a
									href={webResource.url}
									target="_blank"
									rel="noopener noreferrer"
									className="text-blue-500 hover:text-red-600 cursor-pointer text-left font-bold"
									title=""
								>
									{webResource.title.length > 20 ? webResource.title.slice(0, 20) + "..." : webResource.title}
								</a>
							</ToolTip>
						) : (
							<span className="text-gray-700 text-left">{webResource.title.length > 20 ? webResource.title.slice(0, 20) + "..." : marker.content}</span>
						)}						
					</div>
				
				</div>
			);
		});
	};

	const dispatch = useDispatch()
	const { t } = useTranslation('presentation')
	const [isUpdating, setIsUpdating] = useState(false)
	const [showNewSlideSelection, setShowNewSlideSelection] = useState(false)
	const { presentationData, isStreaming } = useSelector(
		(state: RootState) => state.presentationGeneration
	) as { presentationData: PresentationData | null; isStreaming: boolean | null }

	// Get web search resources for reference markers
	// const webSearchResources = presentationData?.webSearchResources
	// const reference_markers = presentationData?.reference_markers
	// Use the centralized group layouts hook
	const { renderSlideContent, loading } = useTemplateLayouts()
	const pathname = usePathname()

	const [slideContentStyle, setSlideContentStyle] = useState({})

	const handleSubmit = async () => {
		const element = document.getElementById(
			`slide-${slide.index}-prompt`
		) as HTMLInputElement
		const value = element?.value
		if (!value?.trim()) {
			toast.error(t('slideContent.enter_prompt_before_submitting'))
			return
		}
		setIsUpdating(true)

		try {
			trackEvent(MixpanelEvent.Slide_Edit_API_Call)
			const response = await PresentationGenerationApi.editSlide(
				slide.id,
				value
			)

			if (response) {
				dispatch(updateSlide({ index: slide.index, slide: response }))
				toast.success(t('slideContent.slide_updated_successfully'))
			}
		} catch (error: any) {
			console.error('Error in slide editing:', error)
			toast.error(t('slideContent.error_in_slide_editing'), {
				description: error.message || t('slideContent.error_in_slide_editing'),
			})
		} finally {
			setIsUpdating(false)
		}
	}
	const onDeleteSlide = async () => {
		try {
			trackEvent(MixpanelEvent.Slide_Delete_API_Call)
			// Add current state to past
			dispatch(
				addToHistory({
					slides: presentationData?.slides,
					actionType: 'DELETE_SLIDE',
				})
			)
			dispatch(deletePresentationSlide(slide.index))
		} catch (error: any) {
			console.error('Error deleting slide:', error)
			toast.error(t('slideContent.error_deleting_slide'), {
				description: error.message || t('slideContent.error_deleting_slide'),
			})
		}
	}
	// Scroll to the new slide when streaming and new slides are being generated
	useEffect(() => {
		if (
			presentationData &&
			presentationData?.slides &&
			presentationData.slides.length > 1 &&
			isStreaming
		) {
			// Scroll to the last slide (newly generated during streaming)
			const lastSlideIndex = presentationData.slides.length - 1
			const slideElement = document.getElementById(
				`slide-${presentationData.slides[lastSlideIndex].index}`
			)
			if (slideElement) {
				slideElement.scrollIntoView({
					behavior: 'smooth',
					block: 'center',
				})
			}
		}

		resizeSlide()
	}, [presentationData?.slides?.length, isStreaming])

	// Memoized slide content rendering to prevent unnecessary re-renders
	const slideContent = useMemo(() => {
		return renderSlideContent(slide, isStreaming ? false : true) // Enable edit mode for main content
	}, [renderSlideContent, slide, isStreaming])

	useEffect(() => {
		if (loading) {
			return
		}
		if (slide.layout.includes('custom')) {
			const existingScript = document.querySelector(
				'script[src*="tailwindcss.com"]'
			)
			if (!existingScript) {
				const script = document.createElement('script')
				script.src = 'https://cdn.tailwindcss.com'
				script.async = true
				document.head.appendChild(script)
			}
		}
	}, [slide, isStreaming, loading])

	function resizeSlide() {
		if (
			presentationData &&
			presentationData?.slides &&
			presentationData.slides.length > 1
		) {
			const slideElement = document.querySelector(
				`[data-name="slide-container"]`
			)
			const width = slideElement?.clientWidth || 0
			if (width > 0 && width < 1280) {
				const scale = width / 1280 || 1
				setSlideContentStyle({
					transform: `scale(${scale})`,
					minWidth: '1280px',
					maxWidth: '1280px',
					minHeight: '720px',
					maxHeight: '720px',
					transformOrigin: 'top left',
				})
				return
			}
		}
		setSlideContentStyle({})
	}

	useEffect(() => {
		resizeSlide()
		window.addEventListener('resize', resizeSlide)
		return () => {
			window.removeEventListener('resize', resizeSlide)
		}
	}, [])

	return (
		<>
			<div
				id={`slide-${slide.index}`}
				data-name="slide-container"
				className="w-full max-w-[1280px] h-fit main-slide flex items-center max-md:mb-4 justify-center relative pointer-events-none md:pointer-events-auto"
			>
				{isStreaming && (
					<Loader2 className="w-8 h-8 absolute right-2 top-2 z-30 text-blue-800 animate-spin" />
				)}
				<div
					data-layout={slide.layout}
					data-group={slide.layout_group}
					className={` w-full  group `}
				>
					{/* render slides */}
					{loading ? (
						<div className="flex flex-col bg-white aspect-video items-center justify-center h-full">
							<Loader2 className="w-8 h-8 animate-spin" />
						</div>
					) : (
						<div className="w-full overflow-hidden aspect-video">
							<div className="w-full" style={slideContentStyle}>
								{slideContent}
							</div>
						</div>
					)}

					{!showNewSlideSelection && (
						<div className="group-hover:opacity-100 hidden md:block opacity-0 transition-opacity my-4 duration-300">
							<ToolTip content={t('slideContent.add_new_slide_below')}>
								{!isStreaming && !loading && (
									<div
										onClick={() => {
											trackEvent(
												MixpanelEvent.Slide_Add_New_Slide_Button_Clicked,
												{ pathname }
											)
											setShowNewSlideSelection(true)
										}}
										className="  bg-white shadow-md w-[80px] py-2 border hover:border-[#5141e5] duration-300  flex items-center justify-center rounded-lg cursor-pointer mx-auto"
									>
										<PlusIcon className="text-gray-500 text-base cursor-pointer" />
									</div>
								)}
							</ToolTip>
						</div>
					)}
					{showNewSlideSelection && !loading && (
						<NewSlide
							index={index}
							templateID={`${slide.layout.split(':')[0]}`}
							setShowNewSlideSelection={setShowNewSlideSelection}
							presentationId={presentationId}
						/>
					)}

					{!isStreaming && !loading && (
						<ToolTip content={t('slideContent.delete_slide')}>
							<div
								onClick={() => {
									trackEvent(MixpanelEvent.Slide_Delete_Slide_Button_Clicked, {
										pathname,
									})
									onDeleteSlide()
								}}
								className="absolute top-2 z-20 sm:top-4 right-2 sm:right-4 hidden md:block  transition-transform"
							>
								<Trash2 className="text-gray-500 text-xl cursor-pointer" />
							</div>
						</ToolTip>
					)}
					{!isStreaming && (
						<div className="absolute top-2 z-20 sm:top-4 hidden md:block left-2 sm:left-4 transition-transform">
							<Popover>
								<PopoverTrigger>
									<ToolTip content={t('slideContent.update_slide_using_prompt')}>
										<div
											className={`p-2 group-hover:scale-105 rounded-lg bg-[#5141e5] hover:shadow-md transition-all duration-300 cursor-pointer shadow-md `}
										>
											<WandSparkles className="w-4 sm:w-5 h-4 sm:h-5 text-white" />
										</div>
									</ToolTip>
								</PopoverTrigger>
								<PopoverContent
									side="right"
									align="start"
									sideOffset={10}
									className="w-[280px] sm:w-[400px] z-20"
								>
									<div className="space-y-4">
										<form
											className="flex flex-col gap-3"
											onSubmit={(e) => {
												e.preventDefault()
												handleSubmit()
											}}
										>
											<Textarea
												id={`slide-${slide.index}-prompt`}
												placeholder={t('slideContent.enter_your_prompt_here')}
												className="w-full min-h-[100px] max-h-[100px] p-2 text-sm border rounded-lg focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
												disabled={isUpdating}
												onKeyDown={(e) => {
													if (e.key === 'Enter' && !e.shiftKey) {
														e.preventDefault()
														handleSubmit()
													}
												}}
												rows={4}
												wrap="soft"
											/>
											<button
												disabled={isUpdating}
												type="submit"
												className={`bg-gradient-to-r from-[#9034EA] to-[#5146E5] rounded-[32px] px-4 py-2 text-white flex items-center justify-end gap-2 ml-auto ${
													isUpdating ? 'opacity-70 cursor-not-allowed' : ''
												}`}
												onClick={() => {
													trackEvent(
														MixpanelEvent.Slide_Update_From_Prompt_Button_Clicked,
														{ pathname }
													)
												}}
											>
												{isUpdating ? t('slideContent.updating') : t('slideContent.update')}
												<SendHorizontal className="w-4 sm:w-5 h-4 sm:h-5" />
											</button>
										</form>
									</div>
								</PopoverContent>
							</Popover>
						</div>
					)}
				{/* Speaker Notes & Reference Markers */}
				{!isStreaming && (
					<div className="absolute top-2 right-8 sm:top-4 sm:right-12 hidden md:flex flex-row items-center gap-3 z-20 transition-transform">
						{slide?.speaker_note && (
							<Popover>
								<PopoverTrigger asChild>
									<div className=" cursor-pointer ">
										<ToolTip content={t('slideContent.show_speaker_notes')}>
											<StickyNote className="text-xl text-gray-500" />
										</ToolTip>
									</div>
								</PopoverTrigger>
								<PopoverContent
									side="left"
									align="start"
									sideOffset={10}
									className="w-[320px] z-30"
								>
									<div className="space-y-2">
										<p className="text-xs font-semibold text-gray-600">
											{t('slideContent.speaker_notes')}
										</p>
										<div className="text-sm text-gray-800 whitespace-pre-wrap max-h-64 overflow-auto">
											{slide.speaker_note}
										</div>
									</div>
								</PopoverContent>
							</Popover>
						)}
						<Popover>
							<PopoverTrigger asChild>
								<div className=" cursor-pointer ">
									<ToolTip content={t('slideContent.show_reference_markers')}>
										<BookOpen className="text-xl text-gray-500" />
									</ToolTip>
								</div>
							</PopoverTrigger>
							<PopoverContent
								side="left"
								align="start"
								sideOffset={10}
								className="w-[320px] z-30"
							>
								<div className="space-y-2">
									<p className="text-xs font-bold text-gray-600">
										{t('slideContent.reference_markers')}
									</p>
								<div className="text-sm text-gray-800 whitespace-pre-wrap max-h-64 overflow-auto space-y-2">
									{renderReferenceMarkersWithResources(slide.index)}
									</div>
								</div>
							</PopoverContent>
						</Popover>
					</div>
				)}
				</div>
			</div>
		</>
	)
}

export default SlideContent
