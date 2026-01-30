import React, { useState, useEffect, useRef } from "react";
import { Stack, TextField } from "@fluentui/react";
import { SendRegular } from "@fluentui/react-icons";
import Send from "../../assets/Send.svg";
import MicrophoneIcon from "../../assets/mic-outline.svg";
import styles from "./QuestionInput.module.css";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faMicrophone } from "@fortawesome/free-solid-svg-icons";

// Available slash commands
const SLASH_COMMANDS = [
  {
    command: "/database",
    description: "Query the database directly",
    example: "/database show top 5 errors",
  },
];

interface Props {
  onSend: (question: string) => void;
  onMicrophoneClick: (e: React.KeyboardEvent | React.MouseEvent) => void;
  onStopClick: (e: React.KeyboardEvent | React.MouseEvent) => void;
  disabled: boolean;
  isSendButtonDisabled: boolean;
  placeholder?: string;
  clearOnSend?: boolean;
  recognizedText: string;
  isListening: boolean;
  isRecognizing: boolean;
  isTextToSpeachActive: boolean;
  setRecognizedText: (text: string) => void;
}

export const QuestionInput = ({
  onSend,
  onMicrophoneClick,
  onStopClick,
  disabled,
  isSendButtonDisabled,
  placeholder,
  clearOnSend,
  recognizedText,
  isListening,
  isRecognizing,
  setRecognizedText,
  isTextToSpeachActive,
}: Props) => {
  const [question, setQuestion] = useState<string>("");
  const [liveRecognizedText, setLiveRecognizedText] = useState<string>("");
  const [microphoneIconActive, setMicrophoneIconActive] =
    useState<boolean>(false);
  const [isMicrophoneDisabled, setIsMicrophoneDisabled] = useState(false);
  const [isTextAreaDisabled, setIsTextAreaDisabled] = useState(false);
  const [showCommandMenu, setShowCommandMenu] = useState(false);
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0);
  const commandMenuRef = useRef<HTMLDivElement>(null);

  // Check if current input should show command menu
  const currentText = question || liveRecognizedText;
  const shouldShowCommandMenu = currentText.startsWith("/") &&
    !currentText.includes(" ") &&
    currentText.length < 12;

  // Filter commands based on input
  const filteredCommands = SLASH_COMMANDS.filter(cmd =>
    cmd.command.toLowerCase().startsWith(currentText.toLowerCase())
  );

  useEffect(() => {
    setShowCommandMenu(shouldShowCommandMenu && filteredCommands.length > 0);
    setSelectedCommandIndex(0);
  }, [currentText, shouldShowCommandMenu, filteredCommands.length]);

  useEffect(() => {
    if (isRecognizing) {
      setLiveRecognizedText(recognizedText);
      setIsTextAreaDisabled(true);
      setMicrophoneIconActive(true);
    } else {
      setIsTextAreaDisabled(false);
      setMicrophoneIconActive(false);
    }
  }, [recognizedText, isRecognizing]);

  useEffect(() => {
    setIsMicrophoneDisabled(isTextToSpeachActive);
  }, [isTextToSpeachActive]);

  const selectCommand = (command: string) => {
    const newText = command + " ";
    setQuestion(newText);
    setLiveRecognizedText(newText);
    setRecognizedText(newText);
    setShowCommandMenu(false);
  };

  const sendQuestion = () => {
    if (disabled || (!question.trim() && !liveRecognizedText.trim())) {
      return;
    }

    const textToSend = question || liveRecognizedText;

    onSend(textToSend);

    if (clearOnSend) {
      setQuestion("");
      setLiveRecognizedText("");
      setRecognizedText("");
    }
  };

  const onEnterPress = (ev: React.KeyboardEvent<Element>) => {
    if (ev.key === "Tab" && showCommandMenu && filteredCommands.length > 0) {
      ev.preventDefault();
      selectCommand(filteredCommands[selectedCommandIndex].command);
      return;
    }

    if (ev.key === "ArrowDown" && showCommandMenu) {
      ev.preventDefault();
      setSelectedCommandIndex(prev =>
        prev < filteredCommands.length - 1 ? prev + 1 : prev
      );
      return;
    }

    if (ev.key === "ArrowUp" && showCommandMenu) {
      ev.preventDefault();
      setSelectedCommandIndex(prev => prev > 0 ? prev - 1 : prev);
      return;
    }

    if (ev.key === "Escape" && showCommandMenu) {
      ev.preventDefault();
      setShowCommandMenu(false);
      return;
    }

    if (ev.key === "Enter" && !ev.shiftKey) {
      if (showCommandMenu && filteredCommands.length > 0) {
        ev.preventDefault();
        selectCommand(filteredCommands[selectedCommandIndex].command);
        return;
      }
      ev.preventDefault();
      sendQuestion();
    }
  };

  const onQuestionChange = (
    _ev: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>,
    newValue?: string
  ) => {
    setQuestion(newValue || "");
    setLiveRecognizedText(newValue || "");
  };

  const sendQuestionDisabled = disabled || !question.trim();

  // Check if we're in database mode
  const isDatabaseMode = currentText.toLowerCase().startsWith("/database ");

  return (
    <Stack horizontal className={styles.questionInputContainer}>
      {/* Command autocomplete menu */}
      {showCommandMenu && filteredCommands.length > 0 && (
        <div className={styles.commandMenu} ref={commandMenuRef}>
          <div className={styles.commandMenuHeader}>Commands</div>
          {filteredCommands.map((cmd, index) => (
            <div
              key={cmd.command}
              className={`${styles.commandMenuItem} ${
                index === selectedCommandIndex ? styles.commandMenuItemSelected : ""
              }`}
              onClick={() => selectCommand(cmd.command)}
              onMouseEnter={() => setSelectedCommandIndex(index)}
            >
              <div className={styles.commandName}>{cmd.command}</div>
              <div className={styles.commandDescription}>{cmd.description}</div>
              <div className={styles.commandExample}>{cmd.example}</div>
            </div>
          ))}
          <div className={styles.commandMenuFooter}>
            Press <kbd>Tab</kbd> or <kbd>Enter</kbd> to select
          </div>
        </div>
      )}

      {/* Database mode indicator */}
      {isDatabaseMode && (
        <div className={styles.databaseModeIndicator}>
          <span className={styles.databaseIcon}>🗄️</span>
          <span>Database Query</span>
        </div>
      )}

      {/* Text Input Field */}
      <TextField
        style={{ backgroundColor: "white" }}
        disabled={isTextAreaDisabled}
        className={styles.questionInputTextArea}
        placeholder={placeholder || "Ask a question or type / for commands..."}
        multiline
        resizable={false}
        borderless
        value={question || liveRecognizedText}
        onChange={(e, newValue) => {
          if (newValue !== undefined) {
            onQuestionChange(e, newValue);
            setRecognizedText(newValue);
          }
        }}
        onKeyDown={onEnterPress}
      />
      <div className={styles.microphoneAndSendContainer}>
        {/* Microphone Icon */}
        <button
          type="button"
          disabled={isMicrophoneDisabled ? true : false}
          className={styles.questionInputMicrophone}
          onClick={
            isListening ? (e) => onStopClick(e) : (e) => onMicrophoneClick(e)
          }
          onKeyDown={(e) =>
            e.key === "Enter" || e.key === " "
              ? isListening
                ? () => onStopClick(e)
                : () => onMicrophoneClick(e)
              : null
          }
          role="button"
          tabIndex={0}
          aria-label="Microphone button"
        >
          {microphoneIconActive || isMicrophoneDisabled ? (
            <FontAwesomeIcon
              icon={faMicrophone}
              className={styles.microphoneIconActive}
              style={{ color: isMicrophoneDisabled ? "lightgray" : "blue" }}
            />
          ) : (
            <img
              src={MicrophoneIcon}
              className={styles.microphoneIcon}
              alt="Microphone"
            />
          )}
        </button>

        {/* Send Button */}
        {isSendButtonDisabled ? (
          <SendRegular className={styles.SendButtonDisabled} />
        ) : (
          <div
            role="button"
            tabIndex={0}
            aria-label="Ask question button"
            onClick={sendQuestion}
            onKeyDown={(e) =>
              e.key === "Enter" || e.key === " " ? sendQuestion() : null
            }
            className={styles.questionInputSendButtonContainer}
          >
            {disabled ? (
              <SendRegular className={styles.questionInputSendButtonDisabled} />
            ) : (
              <img
                src={Send}
                className={styles.questionInputSendButton}
                alt="Send"
              />
            )}
          </div>
        )}
      </div>
    </Stack>
  );
};
