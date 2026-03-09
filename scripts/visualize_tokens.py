"""
Create a pie chart for token breakdown per category.
Usage: python visualize_tokens.py <path_to_folder_with_tokens.json>
"""

import json
import argparse
import os
from pathlib import Path
import plotly.graph_objects as go


def create_token_breakdown_chart(tokens_json_path, output_html_path):
    """
    Create a pie chart from tokens.json data with categories as main slices.
    Each slice shows the breakdown of input, output, and reasoning tokens.
    
    Args:
        tokens_json_path: Path to tokens.json file
        output_html_path: Path to save the HTML chart
    """
    # Load tokens data
    with open(tokens_json_path, 'r') as f:
        tokens_data = json.load(f)
    
    # Extract categories
    categories = tokens_data['by_category']

    # Explicit ordered slices: (category_key, token_type, label, color)
    # Order: Input, Reasoning, Output per category
    slice_order = [
        ('System Prompt',          'input_tokens',           'System Prompt Input',                '#aaaaaa'),
        ('Design Comprehension',   'input_tokens',           'Design Comprehension Input',          '#7ecf7e'),
        ('Design Comprehension',   'reasoning_tokens',       'Design Comprehension Reasoning',      '#4aab4a'),
        ('Design Comprehension',   'visible_output_tokens',  'Design Comprehension Output',         '#1f7a1f'),
        ('Stimulus Generation',    'input_tokens',           'Stimulus Generation Input',           '#7ab8d9'),
        ('Stimulus Generation',    'reasoning_tokens',       'Stimulus Generation Reasoning',       '#3d88c4'),
        ('Stimulus Generation',    'visible_output_tokens',  'Stimulus Generation Output',          '#1a5a9e'),
        ('Agentic Overhead',       'input_tokens',           'Agentic Overhead Input',              '#f5c96a'),
        ('Agentic Overhead',       'reasoning_tokens',       'Agentic Overhead Reasoning',          '#e08a1e'),
        ('Agentic Overhead',       'visible_output_tokens',  'Agentic Overhead Output',             '#a05a00'),
        ('Coverage Feedback',      'input_tokens',           'Coverage Feedback Input',             '#e06060'),
        ('Coverage Feedback',      'reasoning_tokens',       'Coverage Feedback Reasoning',         '#a01a1a'),
        ('Coverage Feedback',      'visible_output_tokens',  'Coverage Feedback Output',            '#f0a0a0'),
    ]

    labels = []
    values = []
    colors = []
    hover_texts = []

    for category_key, token_field, label, color in slice_order:
        if category_key not in categories:
            continue
        count = categories[category_key].get(token_field, 0)
        if count <= 0:
            continue
        labels.append(label)
        values.append(count)
        colors.append(color)
        hover_texts.append(f"<b>{label}</b>")
    
    # Create the figure with a traditional pie chart
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            marker=dict(
                colors=colors,
                line=dict(color='white', width=2)
            ),
            hovertext=hover_texts,
            hoverinfo='text+value',
            textfont=dict(size=10),
            sort=False
        )
    )
    
    # Update layout
    design_name = tokens_data.get('design', 'Design')
    fig.update_layout(
        title=dict(
            text=f"<b>Token Breakdown: {design_name}</b><br>"
                 f"<sub>Categories with Token Type Breakdown (Input/Output/Reasoning)</sub>",
            x=0.5,
            xanchor='center',
            font=dict(size=16)
        ),
        font=dict(size=11),
        height=800,
        width=1000,
        margin=dict(t=100, l=0, r=0, b=0)
    )
    
    # Save the figure
    fig.write_html(output_html_path)
    print(f"Chart saved to: {output_html_path}")
    
    # Print summary statistics
    print(f"Token Breakdown Summary for {design_name}:")
    print("-" * 60)
    for category_name, category_data in categories.items():
        if category_data['total_tokens'] == 0:
            continue
        print(f"\n{category_name}:")
        print(f"  Input:     {category_data['input_tokens']:>8,} tokens")
        print(f"  Output:    {category_data['visible_output_tokens']:>8,} tokens")
        print(f"  Reasoning: {category_data['reasoning_tokens']:>8,} tokens")
        print(f"  Total:     {category_data['total_tokens']:>8,} tokens")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate a token breakdown pie chart from tokens.json',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python visualize_tokens.py c:\\Users\\Vihaan\\PROJECTS\\ASU\\llm-verif\\work\\EVALS\\chacha_top
  python visualize_tokens.py ./work/EVALS/ethmac_eth_with_cop
        """
    )
    parser.add_argument(
        'folder_path',
        type=str,
        help='Path to the folder containing tokens.json'
    )
    
    args = parser.parse_args()
    folder_path = Path(args.folder_path)
    
    # Validate that the folder exists
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"❌ Error: Folder does not exist: {folder_path}")
        exit(1)
    
    # Construct paths
    tokens_path = folder_path / 'tokens.json'
    output_path = folder_path / 'token_breakdown_chart.html'
    
    # Validate that tokens.json exists
    if not tokens_path.exists():
        print(f"❌ Error: tokens.json not found in {folder_path}")
        exit(1)
    
    create_token_breakdown_chart(str(tokens_path), str(output_path))
