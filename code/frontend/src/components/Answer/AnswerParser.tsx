import { AskResponse, Citation } from "../../api";
import { cloneDeep } from "lodash-es";
import { ChartVisualization } from "../DataChart";


type ParsedAnswer = {
    citations: Citation[];
    markdownFormatText: string;
    visualization: ChartVisualization | null;
};

let filteredCitations = [] as Citation[];

// Define a function to check if a citation with the same Chunk_Id already exists in filteredCitations
const isDuplicate = (citation: Citation,citationIndex:string) => {
    return filteredCitations.some((c) => c.chunk_id === citation.chunk_id && c.id === citation.id) ;
};

// Extract visualization config from markdown text
function extractVisualization(text: string): { visualization: ChartVisualization | null; cleanText: string } {
    const vizRegex = /```visualization\n([\s\S]*?)\n```/;
    const match = text.match(vizRegex);

    if (match) {
        try {
            const visualization = JSON.parse(match[1]) as ChartVisualization;
            const cleanText = text.replace(vizRegex, "").trim();
            return { visualization, cleanText };
        } catch (e) {
            console.error("Failed to parse visualization:", e);
        }
    }
    return { visualization: null, cleanText: text };
}

export function parseAnswer(answer: AskResponse): ParsedAnswer {
    let answerText = answer.answer;

    // Extract visualization before processing citations
    const { visualization, cleanText } = extractVisualization(answerText);
    answerText = cleanText;

    const citationLinks = answerText.match(/\[(doc\d\d?\d?)]/g);

    const lengthDocN = "[doc".length;

    filteredCitations = [] as Citation[];
    let citationReindex = 0;
    citationLinks?.forEach(link => {
        // Replacing the links/citations with number
        let citationIndex = link.slice(lengthDocN, link.length - 1);
        let citation = cloneDeep(answer.citations[Number(citationIndex) - 1]) as Citation;
        if (!isDuplicate(citation, citationIndex) && citation !== undefined) {
          answerText = answerText.replaceAll(link, ` ^${++citationReindex}^ `);
          citation.reindex_id = citationReindex.toString(); // reindex from 1 for display
          filteredCitations.push(citation);
        }else{
            // Replacing duplicate citation with original index
            let matchingCitation = filteredCitations.find((ct) => citation.chunk_id === ct.chunk_id && citation.id === ct.id);
            if (matchingCitation) {
                answerText= answerText.replaceAll(link, ` ^${matchingCitation.reindex_id}^ `)
            }
        }
    })


    return {
        citations: filteredCitations,
        markdownFormatText: answerText,
        visualization
    };
}
