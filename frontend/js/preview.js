export function populatedLines(recipient) {
  return [recipient.name, recipient.second_line, recipient.city].filter(value => value.trim());
}

export function createPreview(canvas, configuration) {
  const scale = 2;
  canvas.width = Math.ceil(configuration.page_width * scale);
  canvas.height = Math.ceil(configuration.page_height * scale);
  const context = canvas.getContext('2d');
  const box = configuration.pdf_text_box;

  return recipient => {
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.clearRect(0, 0, configuration.page_width, configuration.page_height);
    context.fillStyle = configuration.color;
    context.font = `${configuration.font_size}px Invitation`;
    context.textBaseline = 'alphabetic';
    const lines = populatedLines(recipient);
    const spacing = configuration.font_size * configuration.line_spacing;
    const ascent = context.measureText('Hgश्रीमती').fontBoundingBoxAscent ?? configuration.font_size;
    lines.forEach((text, index) => {
      const metrics = context.measureText(text);
      context.fillText(text, box.x + (box.width - metrics.width) / 2,
        box.y + 1.5 + index * spacing + ascent);
    });
    return lines;
  };
}