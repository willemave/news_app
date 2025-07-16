// Mark content as read and hide it
async function markAsRead(contentId, element) {
    try {
        const response = await fetch(`/api/content/${contentId}/mark-read`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            // Hide the content element with a fade-out animation
            element.style.transition = 'opacity 0.3s';
            element.style.opacity = '0';
            setTimeout(() => {
                element.style.display = 'none';
            }, 300);
        } else {
            console.error('Failed to mark content as read');
        }
    } catch (error) {
        console.error('Error marking content as read:', error);
    }
}

// Share content using Web Share API or fallback
async function shareContent(title, url, bulletPoints) {
    // Format the share text
    let shareText = `Check out this article: ${title}\n\n`;
    
    // Add key points if available
    if (bulletPoints && bulletPoints.length > 0) {
        shareText += 'Key Points:\n';
        bulletPoints.forEach((point, index) => {
            shareText += `• ${point.text}\n`;
        });
        shareText += '\n';
    }
    
    shareText += `Read more: ${url}`;
    
    // Check if Web Share API is available
    if (navigator.share) {
        try {
            await navigator.share({
                title: title,
                text: shareText,
                url: url
            });
        } catch (error) {
            // User cancelled share or error occurred
            if (error.name !== 'AbortError') {
                console.error('Error sharing:', error);
                fallbackShare(shareText);
            }
        }
    } else {
        // Fallback for browsers that don't support Web Share API
        fallbackShare(shareText);
    }
}

// Fallback share method - copy to clipboard
function fallbackShare(text) {
    // Create a temporary textarea to copy text
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    
    try {
        textarea.select();
        document.execCommand('copy');
        
        // Show feedback to user
        showShareFeedback('Content copied to clipboard!');
    } catch (error) {
        console.error('Failed to copy to clipboard:', error);
        showShareFeedback('Failed to share content');
    } finally {
        document.body.removeChild(textarea);
    }
}

// Show share feedback message
function showShareFeedback(message) {
    // Create feedback element
    const feedback = document.createElement('div');
    feedback.textContent = message;
    feedback.className = 'fixed bottom-4 right-4 bg-gray-800 text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-opacity duration-300';
    document.body.appendChild(feedback);
    
    // Remove after 3 seconds
    setTimeout(() => {
        feedback.style.opacity = '0';
        setTimeout(() => {
            document.body.removeChild(feedback);
        }, 300);
    }, 3000);
}
