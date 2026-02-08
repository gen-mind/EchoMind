"""TensorFlow checkpoint generation for TensorBoard Projector."""

import os
import logging
from typing import Any
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import tensorflow as tf
from tensorboard.plugins import projector

from .exceptions import CheckpointGenerationError


logger = logging.getLogger(__name__)


class CheckpointGenerator:
    """Generate TensorFlow checkpoints from Qdrant vectors."""

    def __init__(self, log_base_dir: str = "/logs"):
        """
        Initialize checkpoint generator.

        Args:
            log_base_dir: Base directory for TensorBoard logs
        """
        self.log_base_dir = log_base_dir

    def generate_visualization(
        self,
        points: list[dict[str, Any]],
        collection_name: str,
    ) -> dict[str, Any]:
        """
        Generate TensorBoard checkpoint and metadata from Qdrant points.

        Args:
            points: List of Qdrant points with 'vector' and 'payload' keys
            collection_name: Name of source collection (for display)

        Returns:
            Dict with 'viz_id', 'log_dir', 'num_points', 'vector_dim'

        Raises:
            CheckpointGenerationError: If generation fails
        """
        if not points:
            raise CheckpointGenerationError("Cannot generate visualization: no points provided")

        try:
            # Extract vectors and validate dimensions
            vectors_list = [p["vector"] for p in points]
            vector_dim = len(vectors_list[0])

            if not all(len(v) == vector_dim for v in vectors_list):
                raise CheckpointGenerationError("All vectors must have same dimensionality")

            vectors = np.array(vectors_list, dtype=np.float32)  # Shape: (N, D)

            # Generate unique viz ID
            viz_id = f"viz-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
            log_dir = os.path.join(self.log_base_dir, viz_id)
            os.makedirs(log_dir, exist_ok=True)

            logger.info(f"📊 Generating visualization {viz_id} with {len(points)} points ({vector_dim}D)")

            # Write metadata.tsv (title + chunk text preview)
            metadata_path = os.path.join(log_dir, "metadata.tsv")
            with open(metadata_path, "w", encoding="utf-8") as f:
                # No header for single-column format (TensorBoard convention)
                for point in points:
                    payload = point.get("payload", {})
                    title = payload.get("title", "Untitled")
                    text = payload.get("text", "")[:100]  # First 100 chars

                    # Combine: "Title | Text preview..."
                    label = f"{title} | {text}".replace("\n", " ").replace("\t", " ")
                    f.write(f"{label}\n")

            logger.info(f"✍️ Wrote metadata for {len(points)} points")

            # Save TensorFlow checkpoint
            embedding = tf.Variable(vectors, name='embedding')
            checkpoint = tf.train.Checkpoint(embedding=embedding)
            checkpoint_path = checkpoint.save(os.path.join(log_dir, "embedding.ckpt"))

            logger.info(f"💾 Saved TensorFlow checkpoint: {checkpoint_path}")

            # Configure TensorBoard Projector
            config = projector.ProjectorConfig()
            emb = config.embeddings.add()
            emb.tensor_name = "embedding/.ATTRIBUTES/VARIABLE_VALUE"
            emb.metadata_path = "metadata.tsv"
            projector.visualize_embeddings(log_dir, config)

            logger.info(f"🎨 Configured TensorBoard Projector")

            return {
                "viz_id": viz_id,
                "log_dir": log_dir,
                "num_points": len(points),
                "vector_dim": vector_dim,
            }

        except CheckpointGenerationError:
            raise
        except Exception as e:
            logger.exception(f"❌ Failed to generate checkpoint")
            raise CheckpointGenerationError(f"Failed to generate checkpoint: {str(e)}") from e
