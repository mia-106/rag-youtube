import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "./button";
import { AlertCircle, X } from "lucide-react";

interface ConfirmationModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    title: string;
    description: string;
    confirmText?: string;
    cancelText?: string;
    variant?: "destructive" | "default";
}

export function ConfirmationModal({
    isOpen,
    onClose,
    onConfirm,
    title,
    description,
    confirmText = "确认",
    cancelText = "取消",
    variant = "destructive",
}: ConfirmationModalProps) {
    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="absolute inset-0 bg-slate-950/40 backdrop-blur-sm"
                    />
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 10 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        exit={{ scale: 0.95, opacity: 0, y: 10 }}
                        className="relative w-full max-w-sm rounded-xl bg-slate-900 border border-slate-800 p-6 shadow-2xl"
                    >
                        <div className="flex items-start gap-4">
                            <div className={`p-2 rounded-full ${variant === "destructive" ? "bg-red-500/10 text-red-400" : "bg-blue-500/10 text-blue-400"}`}>
                                <AlertCircle className="w-5 h-5" />
                            </div>
                            <div className="flex-1">
                                <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
                                <p className="mt-2 text-sm text-slate-400 leading-relaxed">
                                    {description}
                                </p>
                            </div>
                            <button
                                onClick={onClose}
                                className="text-slate-500 hover:text-slate-300 transition-colors"
                                title="关闭"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="mt-8 flex justify-end gap-3">
                            <Button
                                variant="ghost"
                                onClick={onClose}
                                className="text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                            >
                                {cancelText}
                            </Button>
                            <Button
                                variant={variant === "destructive" ? "destructive" : "default"}
                                onClick={() => {
                                    onConfirm();
                                    onClose();
                                }}
                                className={variant === "default" ? "bg-blue-600 hover:bg-blue-700" : ""}
                            >
                                {confirmText}
                            </Button>
                        </div>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    );
}
